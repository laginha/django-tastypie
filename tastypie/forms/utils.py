#!/usr/bin/env python
# encoding: utf-8
import types, re

float_  = re.compile(r'^\-?[0-9]+\.[0-9]+$')

is_serializable   = lambda x: isinstance(x, (int,str,unicode,float,list,dict, types.NoneType))
is_tuple          = lambda x: isinstance(x, tuple)
is_iter           = lambda x: hasattr(x, '__iter__')
is_strfloat       = lambda x: bool( float_.match(x) ) if x else False
is_strint         = lambda x: x.isdigit() if isinstance(x, (unicode,str)) else False
