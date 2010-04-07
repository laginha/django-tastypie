import mimeparse
from django.conf.urls.defaults import patterns, url
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import Paginator, InvalidPage
from django.http import Http404, HttpResponse, HttpResponseRedirect
from tastypie.authentication import Authentication
from tastypie.exceptions import NotFound, BadRequest
from tastypie.http import HttpCreated, HttpAccepted, HttpSeeOther, HttpNotModified, HttpConflict, HttpGone, HttpMethodNotAllowed, HttpNotImplemented, HttpUnauthorized, HttpBadRequest
from tastypie.serializers import Serializer
from tastypie.utils import is_valid_jsonp_callback_value


class Resource(object):
    """
    Mostly for dispatch and responding to requests.
    
    The business logic of what data is available is covered by the
    ``Representation`` object.
    
    Serialization/deserialization is handled "at the edges" (i.e. at the
    beginning/end of the request/response cycle) so that everything internally
    is Python data structures.
    """
    representation = None
    list_representation = None
    detail_representation = None
    serializer = Serializer()
    authentication = Authentication()
    allowed_methods = None
    list_allowed_methods = ['get', 'post', 'put', 'delete']
    detail_allowed_methods = ['get', 'post', 'put', 'delete']
    limit = 20
    api_name = 'nonspecific'
    resource_name = None
    default_format = 'application/json'
    
    def __init__(self, representation=None, list_representation=None,
                 detail_representation=None, serializer=None,
                 authentication=None, allowed_methods=None,
                 list_allowed_methods=None, detail_allowed_methods=None,
                 limit=None, resource_name=None, api_name=None):
        # Shortcut to specify both via arguments.
        if representation is not None:
            self.representation = representation
        
        # Shortcut to specify both at the class level.
        if self.representation is not None:
            self.list_representation = self.representation
            self.detail_representation = self.representation
        
        if list_representation is not None:
            self.list_representation = list_representation
        
        if detail_representation is not None:
            self.detail_representation = detail_representation
        
        if serializer is not None:
            self.serializer = serializer
        
        if authentication is not None:
            self.authentication = authentication
        
        # Shortcut to specify both via arguments.
        if allowed_methods is not None:
            self.allowed_methods = allowed_methods
        
        # Shortcut to specify both at the class level.
        if self.allowed_methods is not None:
            self.list_allowed_methods = self.allowed_methods
            self.detail_allowed_methods = self.allowed_methods
        
        if list_allowed_methods is not None:
            self.list_allowed_methods = list_allowed_methods
        
        if detail_allowed_methods is not None:
            self.detail_allowed_methods = detail_allowed_methods
        
        if limit is not None:
            self.limit = limit
        
        if resource_name is not None:
            self.resource_name = resource_name
        
        if api_name is not None:
            self.api_name = api_name
        
        # Make sure we're good to go.
        if self.list_representation is None:
            raise ImproperlyConfigured("No general representation or specific list representation provided for %r." % self)
        
        if self.detail_representation is None:
            raise ImproperlyConfigured("No general representation or specific detail representation provided for %r." % self)
        
        if self.serializer is None:
            raise ImproperlyConfigured("No serializer provided for %r." % self)
        
        if not self.resource_name:
            raise ImproperlyConfigured("No resource_name provided for %r." % self)
    
    def wrap_view(self, view):
        def wrapper(request, *args, **kwargs):
            return getattr(self, view)(request, *args, **kwargs)
        return wrapper
    
    @property
    def urls(self):
        urlpatterns = patterns('',
            url(r"^(?P<resource_name>%s)/$" % self.resource_name, self.wrap_view('dispatch_list'), name="api_dispatch_list"),
            url(r"^(?P<resource_name>%s)/(?P<obj_id>\d+)/$" % self.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
        )
        return urlpatterns
    
    # FIXME:
    #   - Barkeeper's Friend links?
    
    def determine_format(self, request):
        # First, check if they forced the format.
        if request.GET.get('format'):
            if request.GET['format'] in self.serializer.formats:
                return self.serializer.get_mime_for_format(request.GET['format'])

        # If callback parameter is present, use JSONP.
        if request.GET.has_key('callback'):
            return self.serializer.get_mime_for_format('jsonp')
        
        # Try to fallback on the Accepts header.
        if request.META.get('HTTP_ACCEPT'):
            best_format = mimeparse.best_match(self.serializer.supported_formats, request.META['HTTP_ACCEPT'])
            
            if best_format:
                return best_format
        
        # No valid 'Accept' header/formats. Sane default.
        return self.default_format

    def serialize(self, request, data, format, options=None):
        options = options or {}

        if 'text/javascript' in format:
            # get JSONP callback name. default to "callback"
            callback = request.GET.get('callback', 'callback')
            if not is_valid_jsonp_callback_value(callback):
                raise BadRequest('JSONP callback name is invalid.')
            options['callback'] = callback

        return self.serializer.serialize(data, format, options)

    def deserialize(self, request, data, format='application/json'):
        return self.serializer.deserialize(data, format=request.META.get('CONTENT_TYPE', 'application/json'))
    
    def build_content_type(self, format, encoding='utf-8'):
        if 'charset' in format:
            return format
        
        return "%s; charset=%s" % (format, encoding)
    
    def dispatch_list(self, request, **kwargs):
        request_method = request.method.lower()
        
        if not request_method in self.list_allowed_methods:
            return HttpMethodNotAllowed()
        
        method = getattr(self, "%s_list" % request_method, None)
        
        if method is None:
            return HttpNotImplemented()
        
        auth_result = self.authentication.is_authenticated(request)
        
        if isinstance(auth_result, HttpResponse):
            return auth_result
        
        if not auth_result is True:
            return HttpUnauthorized()
        
        request = convert_post_to_put(request)
        response = method(request)
        
        if not isinstance(response, HttpResponse):
            return HttpAccepted()
        
        return response
    
    def dispatch_detail(self, request, **kwargs):
        request_method = request.method.lower()
        
        if not request_method in self.detail_allowed_methods:
            return HttpMethodNotAllowed
        
        method = getattr(self, "%s_detail" % request_method, None)
        
        if method is None:
            return HttpNotImplemented
        
        auth_result = self.authentication.is_authenticated(request)
        
        if isinstance(auth_result, HttpResponse):
            return auth_result
        
        if not auth_result is True:
            return HttpUnauthorized()
        
        request = convert_post_to_put(request)
        response = method(request, **kwargs)
        
        if not isinstance(response, HttpResponse):
            return HttpAccepted()
        
        return response
    
    def get_list(self, request):
        """
        Should return a HttpResponse (200 OK).
        """
        try:
            offset = int(request.GET.get('offset', 0))
            
            if offset < 0:
                return HttpBadRequest("The starting offset must be >= 0.")
        except ValueError:
            return HttpBadRequest("The starting offset must be an integer.")
        
        try:
            limit = int(request.GET.get('limit', self.limit))
            
            if limit < 0:
                return HttpBadRequest("The limit must be >= 0.")
        except ValueError:
            return HttpBadRequest("The limit must be an integer.")
        
        object_list = {
            'results': [],
            'offset': offset,
            'limit': limit,
        }
        
        # FIXME: Need to pass api_name & resource_name on to the instances.
        for result in self.representation.get_list()[offset:offset + limit]:
            object_list['results'].append(result.to_dict())
        
        desired_format = self.determine_format(request)
        try:
            serialized = self.serialize(request, object_list, desired_format)
        except BadRequest, e:
            return HttpBadRequest(e.args[0])
        return HttpResponse(content=serialized, content_type=self.build_content_type(desired_format))
    
    def get_detail(self, request, obj_id):
        """
        Should return a HttpResponse (200 OK).
        """
        representation = self.representation(api_name=self.api_name, resource_name=self.resource_name)
        
        try:
            representation.get(pk=obj_id)
        except NotFound:
            return HttpGone()
        
        desired_format = self.determine_format(request)
        try:
            serialized = self.serialize(request, representation.to_dict(), desired_format)
        except BadRequest, e:
            return HttpBadRequest(e.args[0])
        return HttpResponse(content=serialized, content_type=self.build_content_type(desired_format))
    
    def put_list(self, request):
        """
        Replaces a collection of resources with another collection.
        Return ``HttpAccepted`` (204 No Content).
        """
        # self.representation.delete()
        # self.representation.update()
        # return HttpAccepted()
        return HttpNotImplemented()
    
    def put_detail(self, request, obj_id):
        """
        If a new resource is created, return ``HttpCreated`` (201 Created).
        If an existing resource is modified, return ``HttpAccepted`` (204 No Content).
        """
        deserialized = self.deserialize(request, request._raw_post_data, format=request.META.get('CONTENT_TYPE', 'application/json'))
        data = {}
        
        for key, value in deserialized.items():
            data[str(key)] = value
        
        representation = self.representation(api_name=self.api_name, resource_name=self.resource_name, data=data)
        
        try:
            representation.update(pk=obj_id)
            return HttpAccepted()
        except:
            representation.create(pk=obj_id)
            return HttpCreated(location=representation.get_resource_uri())
    
    def post_list(self, request):
        """
        If a new resource is created, return ``HttpCreated`` (201 Created).
        """
        # TODO: What to do if the resource already exists at that id? Quietly
        #       update or complain loudly?
        deserialized = self.deserialize(request, request._raw_post_data, format=request.META.get('CONTENT_TYPE', 'application/json'))
        data = {}
        
        for key, value in deserialized.items():
            data[str(key)] = value
        
        representation = self.representation(api_name=self.api_name, resource_name=self.resource_name, data=data)
        representation.create()
        return HttpCreated(location=representation.get_resource_uri())
    
    def post_detail(self, request, obj_id):
        """
        This is not implemented by default because most people's data models
        aren't self-referential.
        
        If a new resource is created, return ``HttpCreated`` (201 Created).
        """
        return HttpNotImplemented()
    
    def delete_list(self, request):
        """
        If the resources are deleted, return ``HttpAccepted`` (204 No Content).
        """
        # TODO: What range ought to be deleted? This seems particularly
        #       dangerous.
        representation = self.representation(api_name=self.api_name, resource_name=self.resource_name)
        # FIXME: This is ModelRepresentation specific and needs abstraction.
        representation.queryset.all().delete()
        return HttpAccepted()
    
    def delete_detail(self, request, obj_id):
        """
        If the resource is deleted, return ``HttpAccepted`` (204 No Content).
        """
        representation = self.representation(api_name=self.api_name, resource_name=self.resource_name)
        
        try:
            representation.delete(pk=obj_id)
            return HttpAccepted()
        except:
            return HttpGone()


# Based off of ``piston.utils.coerce_put_post``. Similarly BSD-licensed.
# And no, the irony is not lost on me.
def convert_post_to_put(request):
    """
    Force Django to process the PUT.
    """
    if request.method == "PUT":
        if hasattr(request, '_post'):
            del request._post
            del request._files
        
        try:
            request.method = "POST"
            request._load_post_and_files()
            request.method = "PUT"
        except AttributeError:
            request.META['REQUEST_METHOD'] = 'POST'
            request._load_post_and_files()
            request.META['REQUEST_METHOD'] = 'PUT'
            
        request.PUT = request.POST
    
    return request