"""Swagger generator
"""
from __future__ import print_function

import optparse
import sys
import re
import string
import logging

import types
import StringIO

import json

from pyang import plugin
from pyang import statements

path_resource_types = ["container", "list", "leaf-list", "leaf"]
delimiter = ""
debug = False
schema_depth = 0

def pyang_plugin_init():
    plugin.register_plugin(SwaggerPlugin())

class SwaggerPlugin(plugin.PyangPlugin):

    def add_output_format(self, fmts):
    	# self.multiple_modules = True
    	fmts['swagger'] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option('--swagger-host',
                                 dest = 'swaggerHost',
                                 default = '127.0.0.1:8080',
                                 help = 'Host to use'),
            optparse.make_option('--swagger-base-path',
                                 dest = 'swaggerBasePath',
                                 default = '/api/running',
                                 help = 'Swagger base path'),
            optparse.make_option('--swagger-scheme',
                                 dest = 'swaggerScheme',
                                 default = 'https',
                                 help = 'Swagger scheme'),
            optparse.make_option('--swagger-schema-depth',
                                 dest = 'swaggerSchemaDepth',
                                 default = '2',
                                 help = 'Swagger schema depth'),
            optparse.make_option('--swagger-schema-title',
                                 dest = 'swaggerSchemaTitle',
                                 default = '',
                                 help = 'Swagger schema title'),
            optparse.make_option('--swagger-schema-version',
                                 dest = 'swaggerSchemaVersion',
                                 default = '0.1',
                                 help = 'Swagger schema version'),
            optparse.make_option('--swagger-debug',
                                 dest = 'swaggerDebug',
                                 action = "store_true",
                                 help = 'Swagger debug'),
            ]

        g = optparser.add_option_group("Swagger specific options")
        g.add_options(optlist)

    def setup_ctx(self, ctx):
        ctx.opts.stmts = None

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
		se = SwaggerEmitter()
		se.emit(ctx, modules)

class SwaggerEmitter(object):
	def emit(self, ctx, modules) :
		global schema_depth
		schema_depth = int(ctx.opts.swaggerSchemaDepth)

		if ctx.opts.swaggerDebug == True:
			logging.basicConfig(level=logging.DEBUG)

		for module in modules:
			print('{')
			print('  "swagger": "2.0",')
			print('  "host": "%s",' % ctx.opts.swaggerHost)
			print('  "basePath": "%s",' % ctx.opts.swaggerBasePath)
			print('  "schemes": ["http"],')
			print('  "info": {')
			print('    "title": "%s",' % ctx.opts.swaggerSchemaTitle)
			print('	   "version": "%s"' % ctx.opts.swaggerSchemaVersion)
			print('  },')
			print('  "paths": {')
			statements.iterate_i_children(module, check_object)
			print('  }')
			print('}')

def check_object(stmt):
	logging.debug("in check_object: %s %s", stmt.arg, stmt.keyword)
	global schema_depth

	if stmt.keyword == "rpc":
	# No support for RPCs
		return "continue"

	depth = check_depth(stmt)
	if depth >= schema_depth:
		return "abort"

	if stmt.keyword in path_resource_types:
		produce_path_object_str(stmt)
	return None

def check_depth(stmt):
	logging.debug("in check_depth with stmt %s %s", stmt.keyword, stmt.arg)
	depth = 0
	s = stmt
	t = stmt.top
	while s is not t:
		s = s.parent
		depth = depth + 1
	return depth - 1

def produce_path_object_str(stmt):
	logging.debug("in produce_path_object_str with stmt %s %s", stmt.keyword, stmt.arg)
	global delimiter
	path = statements.mk_path_str(stmt)

	print('', delimiter)
	delimiter = ','
	print('    "%s": {' % path)
	print('      "get": {')
	print('        "produces": [')
	print('          "application/vnd.yang.data+json",')
	print('          "application/vnd.yang.data+xml"')
	print('        ],')
	print('        "responses": {')
	print('          "200": {')
	print('            "description": "Some description",')
	print('            "schema": {')

	if stmt.keyword == "leaf":
		type, format = type_trans(str(stmt.search_one('type').arg))
		print('              "type": "%s"' % type )

	if stmt.keyword == "list":		
		print('              "type": "array",')
		print('              "items": [')
		for s in stmt.i_children:
			produce_schema_str(s)
		print('              ]')

	if stmt.keyword == "leaf-list":
		type, format = type_trans(str(stmt.search_one('type').arg))
		print('              "type": "array",')
		print('              "items": [')
		print('              	"type": "%s"' % type )		
		print('              ]')

	if stmt.keyword == "container":
		print('              "type": "object",')
		print('				 "properties": {')
		print('                "%s": {' % stmt.arg)
		print('                  "properties": {')
		for s in stmt.i_children:
			produce_schema_str(s)
		print('                  }')
		print('                }')
		print('              }')

	print('            }')
	print('          }')
	print('        }')
	print('      }')
	print('    }')

def produce_schema_str(stmt):
	logging.debug("in produce_schema: %s %s", stmt.keyword, stmt.arg)
	depth =  0
	last = False
	top = stmt

	def _produce_node_iter(stmt, last, top):
		# print "in produce_node_iter: %s" % stmt.keyword, stmt.arg
		path = statements.mk_path_str(stmt)

		if stmt.keyword == "leaf":
			type, format = type_trans(str(stmt.search_one('type').arg))
			if stmt.parent.keyword == "list":
				print('{')
				print('  "type": "object",')
				print('  "properties": {')
			if type == 'enumeration':
				print('"%s": {' % stmt.arg)
				print('  "enum": [')
				for ch in stmt.search("type"):
					for enum in ch.search("enum"):
						if ch.search("enum")[-1] == enum:
							print('"%s"' % enum.arg)
						else:
							print('"%s",' % enum.arg)
				print('  ]')
			else:
				print('"%s": {' % stmt.arg)
				print('  "type": "%s"' % type)
				if format is not None:
					print('  ,"format": "%s"' % format)
			if stmt.parent.keyword == "list":
				print('  }')
				print('  }')
			close_object(stmt, top)

		if stmt.keyword == "leaf-list":
			type, format = type_trans(str(stmt.search_one('type').arg))
			print('"%s": {' % stmt.arg)
			print('  "type": "array",')
			print('  "items": {')
			print('    "type": "%s"' % type)
			print('  }')
			close_object(stmt, top)

		if stmt.keyword == "list":
			print('"%s": {' % stmt.arg)
			print('  "type": "array",')
			print('  "items": [')
			if hasattr(stmt, 'i_children'):
				for s in stmt.i_children:
					_produce_node_iter(s, last, top)
			pass
			print('  ]')
			close_object(stmt, top)

		if stmt.keyword == "container":
			if stmt.parent.keyword == "list":
				print('{')
				print('  "type": "object",')
				print('  "properties": {')
			print('"%s": {' % stmt.arg)
			print('  "type": "object",')
			print('  "properties": {')
			if hasattr(stmt, 'i_children'):
				for s in stmt.i_children:
					_produce_node_iter(s, last, top)
			pass
			print('  }')
			if stmt.parent.keyword == "list":
				print('  }')
				print('  }')
			close_object(stmt, top)
		if stmt.keyword == "choice":
			# XXX: This needs more work, probably around JSON Schema 'oneOf'
			if hasattr(stmt, 'i_children'):
				for s in stmt.i_children:
					_produce_node_iter(s, last, top)
			pass
		if stmt.keyword == "case":
			# XXX: This needs more work, probably around JSON Schema 'oneOf'
			if hasattr(stmt, 'i_children'):
				for s in stmt.i_children:
					_produce_node_iter(s, last, top)
			pass

	_produce_node_iter(stmt, last, top)

def is_last(stmt):
	ignore_parents = ["choice", "case"]
	pp = stmt.parent

	while pp.keyword in ignore_parents:
		pp = pp.parent

	# print "--> path in", statements.mk_path_str(stmt)
	# print "--> parent is: %s %s, last parent i_children is: %s i am: %s" % (pp.keyword, pp.arg, pp.i_children[-1].arg, stmt.arg)

	return pp.i_children[-1] == stmt

def close_object(stmt, top):
	if statements.has_type(stmt, ["enumeration"]):
		print("}")
		return
	if is_last(stmt):
		print("}")
		return
	
	print("},")

def type_trans(type):
	ttype = "string"
	tformat = None
	type_trans_tbl = {
	#	YANG      JSON  schema
		"int8":   ("number", None),
		"int16":  ("number", None),
		"int32":  ("integer", "int32"),
		"int64":  ("integer", "int64"),
		"uint8":  ("number", None),
		"uint16": ("number", None),
		"int32":  ("integer", "int32"),
		"uint64": ("integer", "uint64"),
		"enumeration": "enumeration"
	}
	if type in type_trans_tbl:
		ttype = type_trans_tbl[type][0]
		tformat = type_trans_tbl[type][1]

	return ttype, tformat


