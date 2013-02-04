#!/usr/bin/env python
# encoding: utf-8

class RequiredParamMissing(Exception):
    '''
    For when a required resource parameter is not in request
    '''   
    def __init__(self, param):
        self.param = param
        
    def __nonzero__(self):
        return False

    def __str__(self):
        return "Required parameter '%s' missing from request." %self.param
 
      
class InvalidParameterValue(Exception):
    '''
    For when a parameter value fails the validate test
    '''
    def __init__(self, param, value):
        self.value = value
        self.param = param
    
    def __nonzero__(self):
        return False
    
    def __str__(self):
        expected = self.param.__class__.__name__.replace('Param', '')
        return "Query value '%s' failed %s validation." %(self.value, expected)


class ConversionError(Exception):
    '''
    For when a parameter value could not be properly converted
    '''
    def __init__(self, param, value):
        self.value = value
        self.param = param
    
    def __nonzero__(self):
        return False

    def __str__(self):
        expected = self.param.__class__.__name__.replace('Param', '')
        return "Query value '%s' for '%s' parameter could not be converted properly. %s expected." %(self.value, self.param, expected)


class AndParameterException(Exception):
    '''
    For when not all parameters within an AND are not met/validated
    '''
    alias = 'ApiException'
    
    def __init__(self, params):
        self.params = params
    
    def __nonzero__(self):
        return False
    
    def __str__(self):
        if len(self.params) == 1:
            text = "'%s'" %self.params[0]
        else:
            _lambda = lambda a,b: "%s, '%s'"%(a,b)
            text = reduce(_lambda, self.params[1:-1], "'%s'" %self.params[0])
            text += " and '%s'" %self.params[-1]
        return "Parameters %s cannot be used aloned" %text
