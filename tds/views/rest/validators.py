# Copyright 2016 Ifwe Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A view with validations of parameters given in request queries.
This class is separated out for separation of function.
Its only intended use is as a base class for the BaseView; directly importing
and using this view is discouraged.
"""

import types
import logging
import re

import sqlalchemy.orm.query
import tds.exceptions
from sqlalchemy.orm.exc import NoResultFound
from . import utils
from .json_validators import JSONValidatedView


class ValidatedView(JSONValidatedView):
    """
    This class implements common non-JSON validators.
    """

    def query(self, model):
        """
        Convenience method for creating a query over the model or its delegate
        if creating a query over the model fails.
        Do some duck punching by adding get and find methods to query.
        """
        try:
            query = self.session.query(model)
            has_delegate = False
        except:
            query = self.session.query(model.delegate)
            has_delegate = True

        def get(query, *args, **kwargs):
            try:
                obj = query.filter_by(*args, **kwargs).one()
            except NoResultFound:
                return None
            if has_delegate:
                return model(delegate=obj)
            else:
                return obj

        query.get = types.MethodType(get, query, sqlalchemy.orm.query.Query)
        def find(query, *args, **kwargs):
            if not has_delegate:
                return query.filter_by(*args, **kwargs).all()
            return [model(delegate=obj) for obj in
                    query.filter_by(*args, **kwargs).all()]
        query.find = types.MethodType(find, query, sqlalchemy.orm.query.Query)
        return query

    def _validate_params(self, valid_params):
        """
        Validate all query parameters in self.request against valid_params and
        add a 422 error at 'query'->key if the parameter key is invalid.
        Add validated parameters with values to self.request.validated_params.
        Ignore and drop validated parameters without values (e.g., "?q=&a=").
        """
        if not getattr(self.request, 'validated_params', None):
            self.request.validated_params = dict()

        for key in self.request.params:
            if key not in valid_params:
                self.request.errors.add(
                    'query', key,
                    "Unsupported query: {param}. Valid parameters: "
                    "{all}.".format(param=key, all=sorted(valid_params)),
                )
                self.request.errors.status = 422
            elif self.request.params[key]:
                self.request.validated_params[key] = self.request.params[key]

    def validate_individual(self, request):
        """
        Validate that the resource with the given identifiers exists and
        attach it to the request at request.validated[name].
        This validator can raise a "400 Bad Request" error.
        """
        validator = getattr(
            self,
            'validate_individual_{name}'.format(
                name=self.name.replace('-', '_')
            ),
            None,
        )
        if request.method in ('GET', 'HEAD'):
            param_dict = {'select': 'string'}
            if getattr(self, 'extra_individual_get_params', None) is not None:
                for param in self.extra_individual_get_params:
                    param_dict[param] = self.extra_individual_get_params[param]
            self._validate_params(param_dict.keys())
            self._validate_json_params(param_dict)
        if validator:
            validator(request)
        else:
            if request.method in ("GET", "HEAD"):
                self._validate_params(['select'])
                self._validate_json_params({'select': 'string'})
            self.get_obj_by_name_or_id()

        self._validate_select_attributes(request)

    def validate_collection_get(self, request):
        """
        Make sure that the selection parameters are valid for resource type.
        If they are not, raise "400 Bad Request".
        Else, set request.validated[name] to resource matching query.
        """
        getter = getattr(
            self,
            'validate_{name}_collection'.format(
                name=self.name.replace('-', '_'),
            ),
            None
        )
        if getter is not None:
            getter(request)
        else:
            self.get_collection_by_limit_start()

        self._validate_select_attributes(request)

    def _validate_select_attributes(self, request, valid_attrs=None):
        """
        If the 'select' parameter was passed in the query, validate that the
        comma-separated attributes passed are valid attributes for the model.
        """
        if not (getattr(request, 'validated_params', None) and 'select' in
                request.validated_params):
            return
        if valid_attrs is None:
            valid_attrs = self.full_types.keys()
        if 'select' in request.validated_params:
            request.validated['select'] = request.validated_params[
                'select'
            ].split(',')
            for attr in request.validated['select']:
                if attr not in valid_attrs:
                    request.errors.add(
                        'query', 'select',
                        '{attr} is not a valid attribute. Valid attributes: '
                        '{valid_attrs}.'.format(
                            attr=attr,
                            valid_attrs=sorted(valid_attrs),
                        )
                    )
                    request.errors.status = 400
            del request.validated_params['select']

    def _add_post_defaults(self):
        """
        Add the default values for fields if they are not passed in as params.
        """
        for attr in self.defaults:
            if attr not in self.request.validated_params:
                if type(self.defaults[attr]) == str:
                    self.request.validated_params[attr] = self.defaults[attr]
                else:
                    self.request.validated_params[attr] = self.defaults[attr](
                        self
                    )
        if not getattr(self, 'name', None):
            return
        if 'application' in self.request.validated:
            if 'package' in self.name:
                if 'job' not in self.request.validated_params:
                    self.request.validated_params['job'] = \
                        self.request.validated['application'].path

    def validate_put_post(self, _request):
        """
        Validate a PUT or POST request by validating all given attributes
        against the list of valid attributes for this view's associated model.
        """
        if getattr(self, '_handle_extra_params', None) is not None:
            self._handle_extra_params()
        self._validate_params(self.valid_attrs)
        self._validate_json_params()

    def validate_post_required(self, request):
        """
        Validate that the fields required for a POST are present in the
        parameters of the request.
        """
        for field in self.required_post_fields:
            if field not in request.validated_params:
                request.errors.add(
                    'query', '',
                    "{field} is a required field.".format(field=field)
                )
                request.errors.status = 400

    def validate_obj_put(self, _request):
        """
        Validate a PUT request by preventing collisions over unique fields.
        """
        func_name = 'validate_{name}_put'.format(
            name=self.name.replace('-', '_')
        )
        if getattr(self, func_name, None):
            getattr(self, func_name)()
        else:
            try:
                self._validate_name("PUT")
                self._validate_unique_together("PUT")
                self._validate_all_unique_params("PUT")
            except:
                raise NotImplementedError(
                    'A collision validator for this view has not been '
                    'implemented.'
                )

    def validate_obj_post(self, _request):
        """
        Validate a POST request by preventing collisions over unique fields.
        """
        self._add_post_defaults()
        if not getattr(self, 'name', None):
            return
        func_name = 'validate_{name}_post'.format(
            name=self.name.replace('-', '_')
        )
        if getattr(self, func_name, None):
            getattr(self, func_name)()
        else:
            try:
                self._validate_name("POST")
                self._validate_unique_together("POST")
                self._validate_all_unique_params("POST")
            except:
                raise NotImplementedError(
                    'A collision validator for this view has not been '
                    'implemented.'
                )

    def _validate_unique_together(self, request_type, obj_type=None):
        """
        Validate that any unique together constraints aren't violated.
        """
        if getattr(self, 'unique_together', None) is None:
            return
        if request_type == "PUT" and self.name not in self.request.validated:
            return
        if not obj_type:
            obj_type = self.name
        for tup in self.unique_together:
            tup_dict = dict()
            for item in tup:
                key = self.param_routes.get(item, item)
                if request_type == "POST" and item not in \
                        self.request.validated_params:
                    continue
                tup_dict[key] = self.request.validated_params[item] if item \
                    in self.request.validated_params else \
                    getattr(self.request.validated[self.name], key)
            found = self.query(self.model).get(**tup_dict)
            if found is not None:
                if request_type == "POST":
                    self.request.errors.add(
                        'query', tup[-1],
                        "{tup} are unique together. A{mult} {obj_type} with "
                        "these attributes already exists.".format(
                            tup=tup,
                            mult='n' if obj_type[0] in 'aeiou' else '',
                            obj_type=obj_type,
                        )
                    )
                    self.request.errors.status = 409
                elif request_type == "PUT" and found != self.request.validated[
                    self.name
                ]:
                    self.request.errors.add(
                        'query', tup[-1],
                        "{tup} are unique together. Another {obj_type} with "
                        "these attributes already exists.".format(
                            tup=tup,
                            obj_type=obj_type,
                        )
                    )
                    self.request.errors.status = 409

    def _validate_all_unique_params(self, request_type):
        """
        Validate all unique params if the view contains a unique attribute.
        """
        if getattr(self, 'unique', None) is None:
            return
        for param in self.unique:
            self._validate_unique_param(request_type, param)

    def _validate_name(self, request_type, obj_type=None):
        """
        Validate that the name unique constraint isn't violated for a request
        with either POST or PUT request_type.
        """
        self._validate_unique_param(request_type, "name", obj_type)

    def _validate_unique_param(self, request_type, param_name, obj_type=None,
                               msg_param_name=None):
        """
        Validate that a parameter is unique in the database.
        request_type is "(POST|PUT)".
        param_name is the API exposed name for the attribute and should be in
        self.request.validated_params.
        obj_type is the model or None if self.model.
        msg_param_name is the param name to use in the error message.
        """
        if not obj_type:
            obj_type = self.name
        if not msg_param_name:
            msg_param_name = param_name
        if param_name in self.request.validated_params:
            dict_key = self.param_routes[param_name] if param_name in \
                self.param_routes else param_name
            found_obj = self.query(self.model).get(
                **{dict_key: self.request.validated_params[param_name]}
            )
            if not found_obj:
                return
            elif request_type == 'POST':
                self.request.errors.add(
                    'query', param_name,
                    "Unique constraint violated. A{n} {type} with this {param}"
                    " already exists.".format(
                        n='n' if obj_type[0] in 'aeiou' else '',
                        type=obj_type,
                        param=msg_param_name,
                    )
                )
            elif obj_type not in self.request.validated:
                return
            elif found_obj != self.request.validated[obj_type]:
                self.request.errors.add(
                    'query', param_name,
                    "Unique constraint violated. Another {type} with this "
                    "{param} already exists.".format(
                        type=obj_type,
                        param=msg_param_name,
                    )
                )
            self.request.errors.status = 409

    def validate_obj_delete(self, request):
        """
        Validate that the object can be deleted.
        """
        func_name = 'validate_{name}_delete'.format(
            name=getattr(self, 'name', '').replace('-', '_')
        )
        if getattr(self, func_name, None) is not None:
            self._validate_params(['cascade'])
            self._validate_json_params({'cascade': 'boolean'})
            request.validated['cascade'] = 'cascade' in \
                request.validated_params and request.validated_params['cascade']
            getattr(self, func_name)()
        else:
            return self.method_not_allowed(request)

    def validate_cookie(self, request):
        """
        Validate the cookie in the request. If the cookie is valid, add a user
        to the request's validated_params dictionary.
        If the user is not authorized to do the current action, add the
        corresponding error.
        """
        (present, username, is_admin, restrictions) = utils.validate_cookie(
            request,
            self.settings
        )
        if not present:
            request.errors.add(
                'header', 'cookie',
                'Authentication required. Please login.'
            )
            if request.errors.status == 400:
                request.errors.status = 401
        elif not username:
            request.errors.add(
                'header', 'cookie',
                'Cookie has expired or is invalid. Please reauthenticate.'
            )
            if request.errors.status == 400:
                request.errors.status = 419
        else:
            request.validated['user'] = username
            request.is_admin = is_admin
            for key in restrictions:
                restrictions[key] = restrictions[key].split('+')
            request.restrictions = restrictions
            try:
                collection_path = self.settings['url_prefix'] + \
                    self._services[
                        'collection_{name}'.format(
                            name=self.__class__.__name__.lower()
                        )
                    ].path
            except KeyError:
                collection_path = None

            # Change URL parameters to regexes and check if the actual path
            # matches the newly constructed regex to determine if the path of
            # this request is the collection path.
            if collection_path is not None:
                url_placeholder = re.compile(r'\{[a-zA-Z0-9_-]*\}')
                url_matcher = re.compile(
                    url_placeholder.sub('[a-zA-Z0-9_-]*', collection_path) +
                    '$'
                )
                prefix = "collection_" if url_matcher.match(request.path) \
                    else ''
            else:
                prefix = ''
            if not getattr(self, 'permissions', None):
                logging.warning(
                    "Permissions dictionary is required, could not be found."
                )
                return self.method_not_allowed(request)
            permissions_key = prefix + request.method.lower()
            if permissions_key not in self.permissions:
                logging.warning(
                    "Could not find permissions entry for {perm_key}.".format(
                        perm_key=permissions_key,
                    )
                )
                return self.method_not_allowed(request)
            if self.permissions[permissions_key] == 'not allowed':
                return self.method_not_allowed(request)
            elif self.permissions[permissions_key] == 'admin':
                if not request.is_admin:
                    request.errors.add(
                        'header', 'cookie',
                        'Admin authorization required. Please contact someone '
                        'in SiteOps to perform this operation for you.'
                    )
                    request.errors.status = 403
            if 'methods' in request.restrictions:
                request_method = 'get' if request.method == 'HEAD' else \
                    request.method
                if not any(request_method.lower() == method.lower() for method
                           in request.restrictions['methods']):
                    request.errors.add(
                        'header', 'cookie',
                        'Insufficient authorization. This cookie only has '
                        'permissions for the following privileged methods: '
                        '{methods}.'.format(
                            methods=sorted(
                                str(method) for method in
                                request.restrictions['methods']
                            ),
                        )
                    )
                    request.errors.status = 403

    def _validate_foreign_key(self, param_name, model_name, model,
                              attr_name=None):
        """
        Validate that a foreign key object with the name or ID in
        self.request.validated_params.
        If param_name is not in validated_params, just return.
        If an object with the name or ID can't be found, add an error to
        self.request.errors and set the status to 400.
        If attr_name is give, look for the name at that field in the model;
        otherwise, look in model.name
        """
        if param_name not in self.request.validated_params:
            return
        found = self._validate_foreign_key_existence(
            param_name,
            self.request.validated_params[param_name],
            model,
            model_name,
            attr_name
        )
        if found:
            self.request.validated_params[param_name] = found.id

    def _validate_foreign_key_existence(self, param_name, param, model,
                                        model_name, attr_name=None):
        """
        Verify that an object of type model with the given model_name exists
        and return it if it does.
        If it doesn't, set an error and return False
        """
        try:
            obj_id = int(param)
            found = self.query(model).get(id=obj_id)
            if found is None:
                self.request.errors.add(
                    'query', param_name,
                    "No {type} with ID {obj_id} exists.".format(
                        type=model_name,
                        obj_id=obj_id,
                    )
                )
                self.request.errors.status = 400
                return False
            return found
        except ValueError:
            name = param
            attrs = {attr_name: name} if attr_name else {'name': name}
            found = self.query(model).get(**attrs)
            if found is None:
                self.request.errors.add(
                    'query', param_name,
                    "No {type} with name {name} exists.".format(
                        type=model_name,
                        name=name
                    )
                )
                self.request.errors.status = 400
                return False
            return found

    def _validate_foreign_key_list(self, param_name, model_name, model,
                                   attr_name=None):
        """
        Validate the list or individual foreign key.
        """
        if param_name not in self.request.validated_params:
            return
        identifiers = self.request.validated_params[param_name].split(',')
        found_list = list()
        for identifier in identifiers:
            found = self._validate_foreign_key_existence(
                param_name,
                identifier,
                model,
                model_name,
                attr_name
            )
            if found:
                found_list.append(found)
        self.request.validated_params[param_name] = found_list

    def method_not_allowed(self, request):
        """
        Validator used to make methods not valid for a URL.
        """
        request.errors.add('url', 'method', "Method not allowed.")
        request.errors.status = 405

    def _add_individual_options(self, request):
        """
        Add options to self.result.
        """
        self.result = self.individual_allowed_methods
        self.result['OPTIONS'] = dict(
            description="Get HTTP method options and parameters for this URL "
                "endpoint.",
            permissions='none',
        )

        if 'GET' in self.result:
            self.result['GET']['parameters'] = dict(
                select=dict(
                    type='CSV',
                    description="Comma-separated list of attributes to return",
                )
            )
            self.result['GET']['attributes'] = dict()
            for attr in self.full_types:
                self.result['GET']['attributes'][attr] = dict(
                    type=self.full_types[attr],
                    description=self.full_descriptions[attr],
                )

        if 'PUT' in self.result:
            self.result['PUT']['parameters'] = dict()
            for attr in self.types:
                self.result['PUT']['parameters'][attr] = dict(
                    type=self.types[attr],
                    description=self.param_descriptions[attr],
                )
            if 'returns' not in self.result['PUT']:
                self.result['PUT']['returns'] = "Updated {name}".format(
                    name=self.name
                )
            for attr in getattr(self, 'unique', list()):
                self.result['PUT']['parameters'][attr]['unique'] = True
            if getattr(self, 'unique_together', None) is not None:
                self.result['PUT']['unique_together'] = sorted(
                    self.unique_together
                )

        if 'POST' in self.result:
            self.result['POST']['parameters'] = dict()
            for attr in self.types:
                self.result['POST']['parameters'][attr] = dict(
                    type=self.types[attr],
                    description=self.param_descriptions[attr]
                )
            if 'returns' not in self.result['POST']:
                self.result['POST']['returns'] = 'Newly created {name}'.format(
                    name=self.name
                )
            for attr in getattr(self, 'required_post_fields', list()):
                self.result['POST']['parameters'][attr]['required'] = True
            for attr in getattr(self, 'unique', list()):
                self.result['POST']['parameters'][attr]['unique'] = True
            if getattr(self, 'unique_together', None) is not None:
                self.result['POST']['unique_together'] = sorted(
                    self.unique_together
                )

        if 'DELETE' in self.result:
            if 'returns' not in self.result['DELETE']:
                self.result['DELETE']['returns'] = "Deleted {name}".format(
                    name=self.name
                )

        for method in self.result:
            if 'permissions' in self.result[method]:
                continue
            if getattr(self, 'permissions', None) and method.lower() in \
                    self.permissions:
                self.result[method]['permissions'] = self.permissions[
                    method.lower()
                ]
            else:
                self.result[method]['permissions'] = 'user'

        if getattr(self, '_add_additional_individual_options', None) is not \
                None:
            getattr(self, '_add_additional_individual_options')(request)

    def validate_individual_options(self, request):
        """
        If the subclass has the appropriate method, call it.
        Otherwise, do some generic options information setup to be returned.
        """
        getattr(
            self,
            'validate_individual_{name}_options'.format(
                name=self.name.replace('-', '_')
            ),
            self._add_individual_options,
        )(request)

    def _add_collection_options(self, request):
        """
        Add options to self.result.
        """
        self.result = self.collection_allowed_methods
        self.result['OPTIONS'] = dict(
            description="Get HTTP method options and parameters for this URL "
                "endpoint.",
            permissions='none',
        )

        if 'GET' in self.result:
            self.result['GET']['attributes'] = dict()
            for attr in self.full_types:
                self.result['GET']['attributes'][attr] = dict(
                    type=self.full_types[attr],
                    description=self.full_descriptions[attr],
                )
            self.result['GET']['parameters'] = dict(
                limit=dict(
                    type='integer',
                    description='Maximum number of items to return',
                ),
                start=dict(
                    type='integer',
                    description='ID of where to start the list'
                ),
                select=dict(
                    type='CSV',
                    description="Comma-separated list of attributes to return",
                )
            )

        if 'POST' in self.result:
            self.result['POST']['parameters'] = dict()
            for attr in self.types:
                self.result['POST']['parameters'][attr] = dict(
                    types=self.types[attr],
                    description=self.param_descriptions[attr],
                )
            if 'returns' not in self.result['POST']:
                self.result['POST']['returns'] = "Newly created {name}".format(
                    name=self.name
                )

            for attr in getattr(self, 'required_post_fields', list()):
                self.result['POST']['parameters'][attr]['required'] = True
            for attr in getattr(self, 'unique', list()):
                self.result['POST']['parameters'][attr]['unique'] = True
            if getattr(self, 'unique_together', None) is not None:
                self.result['POST']['unique_together'] = sorted(
                    self.unique_together
                )

        for method in self.result:
            if 'permissions' in self.result[method]:
                continue
            if getattr(self, 'permissions', None) and \
                    'collection_{method}'.format(method=method.lower()) in \
                    self.permissions:
                self.result[method]['permissions'] = self.permissions[
                    'collection_{method}'.format(method=method.lower())
                ]
            else:
                self.result[method]['permissions'] = 'user'

        if getattr(self, '_add_additional_collection_options', None) is not \
                None:
            getattr(self, '_add_additional_collection_options')(request)

    def validate_collection_options(self, request):
        """
        If the subclass has the appropriate method, call it.
        Otherwise, do some generic options informations setup to be returned.
        """
        getattr(
            self,
            'validate_collection_{name}_options'.format(
                name=self.name.replace('-', '_')
            ),
            self._add_collection_options,
        )(request)
