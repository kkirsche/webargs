"""Tornado request argument parsing module.

Example: ::

    import tornado.web
    from marshmallow import fields
    from webargs.tornadoparser import use_args

    class HelloHandler(tornado.web.RequestHandler):

        @use_args({'name': fields.Str(missing='World')})
        def get(self, args):
            response = {'message': 'Hello {}'.format(args['name'])}
            self.write(response)
"""
import tornado.web
import tornado.concurrent
from tornado.escape import _unicode

from webargs import core
from webargs.multidictproxy import MultiDictProxy


class HTTPError(tornado.web.HTTPError):
    """`tornado.web.HTTPError` that stores validation errors."""

    def __init__(self, *args, **kwargs):
        self.messages = kwargs.pop("messages", {})
        self.headers = kwargs.pop("headers", None)
        super().__init__(*args, **kwargs)


def is_json_request(req):
    content_type = req.headers.get("Content-Type")
    return content_type is not None and core.is_json(content_type)


class WebArgsTornadoMultiDictProxy(MultiDictProxy):
    """
    Override class for Tornado multidicts, handles argument decoding
    requirements.
    """

    def __getitem__(self, key):
        try:
            value = self.data.get(key, core.missing)
            if value is core.missing:
                return core.missing
            if key in self.multiple_keys:
                return [
                    _unicode(v) if isinstance(v, (str, bytes)) else v for v in value
                ]
            if value and isinstance(value, (list, tuple)):
                value = value[0]

            if isinstance(value, (str, bytes)):
                return _unicode(value)
            return value
        # based on tornado.web.RequestHandler.decode_argument
        except UnicodeDecodeError:
            raise HTTPError(400, f"Invalid unicode in {key}: {value[:40]!r}")


class WebArgsTornadoCookiesMultiDictProxy(MultiDictProxy):
    """
    And a special override for cookies because they come back as objects with a
    `value` attribute we need to extract.
    Also, does not use the `_unicode` decoding step
    """

    def __getitem__(self, key):
        cookie = self.data.get(key, core.missing)
        if cookie is core.missing:
            return core.missing
        if key in self.multiple_keys:
            return [cookie.value]
        return cookie.value


class TornadoParser(core.Parser):
    """Tornado request argument parser."""

    def _raw_load_json(self, req):
        """Return a json payload from the request for the core parser's load_json

        Checks the input mimetype and may return 'missing' if the mimetype is
        non-json, even if the request body is parseable as json."""
        if not is_json_request(req):
            return core.missing

        # request.body may be a concurrent.Future on streaming requests
        # this would cause a TypeError if we try to parse it
        if isinstance(req.body, tornado.concurrent.Future):
            return core.missing

        return core.parse_json(req.body)

    def load_querystring(self, req, schema):
        """Return query params from the request as a MultiDictProxy."""
        return self._makeproxy(
            req.query_arguments, schema, cls=WebArgsTornadoMultiDictProxy
        )

    def load_form(self, req, schema):
        """Return form values from the request as a MultiDictProxy."""
        return self._makeproxy(
            req.body_arguments, schema, cls=WebArgsTornadoMultiDictProxy
        )

    def load_headers(self, req, schema):
        """Return headers from the request as a MultiDictProxy."""
        return self._makeproxy(req.headers, schema, cls=WebArgsTornadoMultiDictProxy)

    def load_cookies(self, req, schema):
        """Return cookies from the request as a MultiDictProxy."""
        # use the specialized subclass specifically for handling Tornado
        # cookies
        return self._makeproxy(
            req.cookies, schema, cls=WebArgsTornadoCookiesMultiDictProxy
        )

    def load_files(self, req, schema):
        """Return files from the request as a MultiDictProxy."""
        return self._makeproxy(req.files, schema, cls=WebArgsTornadoMultiDictProxy)

    def handle_error(self, error, req, schema, *, error_status_code, error_headers):
        """Handles errors during parsing. Raises a `tornado.web.HTTPError`
        with a 400 error.
        """
        status_code = error_status_code or self.DEFAULT_VALIDATION_STATUS
        if status_code == 422:
            reason = "Unprocessable Entity"
        else:
            reason = None
        raise HTTPError(
            status_code,
            log_message=str(error.messages),
            reason=reason,
            messages=error.messages,
            headers=error_headers,
        )

    def _handle_invalid_json_error(self, error, req, *args, **kwargs):
        raise HTTPError(
            400,
            log_message="Invalid JSON body.",
            reason="Bad Request",
            messages={"json": ["Invalid JSON body."]},
        )

    def get_request_from_view_args(self, view, args, kwargs):
        return args[0].request


parser = TornadoParser()
use_args = parser.use_args
use_kwargs = parser.use_kwargs
