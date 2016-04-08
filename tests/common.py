# -*- coding: utf-8 -*-
import json

import marshmallow
import pytest
import webtest

MARSHMALLOW_VERSION_INFO = marshmallow.__version__.split('.')

class CommonTestCase(object):
    """Base test class that defines test methods for common functionality across all
    parsers. Subclasses must define `create_app`, which returns a WSGI-like app.
    """

    def create_app(self):
        """Return a WSGI app"""
        raise NotImplementedError('Must define create_app()')

    def create_testapp(self, app):
        return webtest.TestApp(app)

    @pytest.fixture(scope='class')
    def testapp(self):
        return self.create_testapp(self.create_app())

    def test_parse_querystring_args(self, testapp):
        assert testapp.get('/echo?name=Fred').json == {'name': 'Fred'}

    def test_parse_querystring_with_query_location_specified(self, testapp):
        assert testapp.get('/echo_query?name=Steve').json == {'name': 'Steve'}

    def test_parse_form(self, testapp):
        assert testapp.post('/echo', {'name': 'Joe'}).json == {'name': 'Joe'}

    def test_parse_json(self, testapp):
        assert testapp.post_json('/echo', {'name': 'Fred'}).json == {'name': 'Fred'}

    def test_parse_querystring_default(self, testapp):
        assert testapp.get('/echo').json == {'name': 'World'}

    def test_parse_json_default(self, testapp):
        assert testapp.post_json('/echo', {}).json == {'name': 'World'}

    def test_parse_json_with_charset(self, testapp):
        res = testapp.post('/echo',
                           json.dumps({'name': 'Steve'}),
                           content_type='application/json;charset=UTF-8')
        assert res.json == {'name': 'Steve'}

    def test_parse_json_with_vendor_media_type(self, testapp):
        res = testapp.post('/echo',
                           json.dumps({'name': 'Steve'}),
                           content_type='application/vnd.api+json;charset=UTF-8')
        assert res.json == {'name': 'Steve'}

    def test_parse_json_ignores_extra_data(self, testapp):
        assert testapp.post_json('/echo', {'extra': 'data'}).json == {'name': 'World'}

    def test_parse_json_blank(self, testapp):
        assert testapp.post_json('/echo', None).json == {'name': 'World'}

    def test_parse_json_ignore_unexpected_int(self, testapp):
        assert testapp.post_json('/echo', 1).json == {'name': 'World'}

    def test_parse_json_ignore_unexpected_list(self, testapp):
        assert testapp.post_json('/echo', [{'extra': 'data'}]).json == {'name': 'World'}

    def test_parse_json_many_schema_invalid_input(self, testapp):
        res = testapp.post_json('/echo_many_schema', [{'name': 'a'}], expect_errors=True)
        assert res.status_code == 422

    def test_parse_json_many_schema(self, testapp):
        res = testapp.post_json('/echo_many_schema', [{'extra': 'data'}]).json
        assert res == [{'name': 'World'}]

    def test_parse_json_many_schema_ignore_malformed_data(self, testapp):
        assert testapp.post_json('/echo_many_schema', {'extra': 'data'}).json == []

    def test_parsing_form_default(self, testapp):
        assert testapp.post('/echo', {}).json == {'name': 'World'}

    def test_parse_querystring_multiple(self, testapp):
        expected = {'name': ['steve', 'Loria']}
        assert testapp.get('/echo_multi?name=steve&name=Loria').json == expected

    def test_parse_form_multiple(self, testapp):
        expected = {'name': ['steve', 'Loria']}
        assert testapp.post('/echo_multi', {'name': ['steve', 'Loria']}).json == expected

    def test_parse_json_list(self, testapp):
        expected = {'name': ['Steve']}
        assert testapp.post_json('/echo_multi', {'name': 'Steve'}).json == expected

    def test_parse_json_with_nonascii_chars(self, testapp):
        text = u'øˆƒ£ºº∆ƒˆ∆'
        assert testapp.post_json('/echo', {'name': text}).json == {'name': text}

    def test_validation_error_returns_422_response(self, testapp):
        res = testapp.post('/echo', {'name': 'b'}, expect_errors=True)
        assert res.status_code == 422

    def test_user_validation_error_returns_422_response_by_default(self, testapp):
        res = testapp.post_json('/error', {'text': 'foo'}, expect_errors=True)
        assert res.status_code == 422

    @pytest.mark.skipif(int(MARSHMALLOW_VERSION_INFO[1]) < 7,
                        reason='status_code only works in marshmallow>=2.7')
    def test_user_validation_error_with_status_code(self, testapp):
        res = testapp.post_json('/error400', {'text': 'foo'}, expect_errors=True)
        assert res.status_code == 400

    def test_use_args_decorator(self, testapp):
        assert testapp.get('/echo_use_args?name=Fred').json == {'name': 'Fred'}

    def test_use_args_with_path_param(self, testapp):
        url = '/echo_use_args_with_path_param/foo'
        res = testapp.get(url + '?value=42')
        assert res.json == {'value': 42}

    def test_use_args_with_validation(self, testapp):
        result = testapp.post('/echo_use_args_validated', {'value': 43})
        assert result.status_code == 200
        result = testapp.post('/echo_use_args_validated', {'value': 41}, expect_errors=True)
        assert result.status_code == 422

    def test_use_kwargs_decorator(self, testapp):
        assert testapp.get('/echo_use_kwargs?name=Fred').json == {'name': 'Fred'}

    def test_use_kwargs_with_path_param(self, testapp):
        url = '/echo_use_kwargs_with_path_param/foo'
        res = testapp.get(url + '?value=42')
        assert res.json == {'value': 42}

    def test_parsing_headers(self, testapp):
        res = testapp.get('/echo_headers', headers={'name': 'Fred'})
        assert res.json == {'name': 'Fred'}

    def test_parsing_cookies(self, testapp):
        testapp.set_cookie('name', 'Steve')
        res = testapp.get('/echo_cookie')
        assert res.json == {'name': 'Steve'}

    def test_parse_nested_json(self, testapp):
        res = testapp.post_json('/echo_nested', {
            'name': {'first': 'Steve', 'last': 'Loria'}
        })
        assert res.json == {'name': {'first': 'Steve', 'last': 'Loria'}}

    def test_parse_nested_many_json(self, testapp):
        in_data = {'users': [{'id': 1, 'name': 'foo'}, {'id': 2, 'name': 'bar'}]}
        res = testapp.post_json('/echo_nested_many', in_data)
        assert res.json == in_data

    def test_parse_json_if_no_json(self, testapp):
        res = testapp.post('/echo')
        assert res.json == {'name': 'World'}

    def test_parse_files(self, testapp):
        res = testapp.post('/echo_file', {'myfile': webtest.Upload('README.rst', b'data')})
        assert res.json == {'myfile': 'data'}