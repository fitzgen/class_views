from django.http import HttpResponseRedirect

# This shouldn't be necessary once class based views make it in to django trunk,
# but till then we need a way to reuse decorators between functions and views.
# http://www.toddreed.name/content/django-view-class/
def decorate_method_with(function_decorator):
    """
    This allows seemless re-use of decorators between functions and methods.
    """
    def decorate_method(unbound_method):
        def method_proxy(self, *args, **kwargs):
            def f(*a, **kw):
                return unbound_method(self, *a, **kw)
            return function_decorator(f)(*args, **kwargs)
        return method_proxy
    return decorate_method

class GenericView(object):
    """
    Parent class for all generic views.

    This was written by jacobian, don't use this directly, use ObjectView.
    """

    def __init__(self, **kwargs):
        self._load_config_values(kwargs,
            context_processors = None,
            mimetype = 'text/html',
            template_loader = None,
            template_name = None
        )
        if kwargs:
            raise TypeError("__init__() got an unexpected keyword argument '%s'" % iter(kwargs).next())

    def __call__(self, request, object=None):
        template = self.get_template(request, object)
        context = self.get_context(request, object)
        mimetype = self.get_mimetype(request, object)
        response = self.get_response(request, object, template, context, mimetype=mimetype)
        return response

    def get_template(self, request, obj):
        """
        Get a ``Template`` object for the given request.
        """
        names = self.get_template_names(request, obj)
        if not names:
            raise ImproperlyConfigured("'%s' must provide template_name." % self.__class__.__name__)
        return self.load_template(request, obj, names)

    def get_template_names(self, request, obj):
        """
        Return a list of template names to be used for the request. Must return
        a list. May not be called if get_template is overridden.
        """
        if self.template_name is None:
            return []
        elif isinstance(self.template_name, basestring):
            return [self.template_name]
        else:
            return self.template_name

    def load_template(self, request, obj, names=[]):
        """
        Load a template, using self.template_loader or the default.
        """
        return self.get_template_loader(request, obj).select_template(names)

    def get_template_loader(self, request, obj):
        """
        Get the template loader to be used for this request. Defaults to
        ``django.template.loader``.
        """
        import django.template.loader
        return self.template_loader or django.template.loader

    def get_context(self, request, obj, context=None):
        """
        Get the context. Must return a Context (or subclass) instance.
        """
        processors = self.get_context_processors(request, obj)
        if context is None:
            context = {}
        return RequestContext(request, context, processors)

    def get_context_processors(self, request, obj):
        """
        Get the context processors to be used for the given request.
        """
        return self.context_processors

    def get_mimetype(self, request, obj):
        """
        Get the mimetype to be used for the given request.
        """
        return self.mimetype

    def get_response(self, request, obj, template, context, **httpresponse_kwargs):
        """
        Construct an `HttpResponse` object given the template and context.
        """
        return HttpResponse(template.render(context), **httpresponse_kwargs)

    def _load_config_values(self, initkwargs, **defaults):
        """
        Set on self some config values possibly taken from __init__, or
        attributes on self.__class__, or some default.
        """
        for k in defaults:
            default = getattr(self.__class__, k, defaults[k])
            value = initkwargs.pop(k, default)
            setattr(self, k, value)


class HttpRedirect(Exception):
    """
    Raise this exception from within a method in an ObjectView to redirect
    the user to a new page.
    """
    def __init__(self, path, *args, **kwargs):
        super(Exception, self).__init__(path, *args, **kwargs)
        self.redirect = HttpResponseRedirect(path)

class ObjectViewMeta(type):
    """
    We need to use this meta class to define decorators on ObjectViews.
    """
    def __new__(mcs, name, bases, attrs):
        cls = type.__new__(mcs, name, bases, attrs)
        if hasattr(cls, "decorators"):
            decorators = list(cls.decorators)
            decorators.reverse()
            for d in decorators:
                cls.__call__ = d(cls.__call__)
        return cls

class ObjectView(GenericView):
    """
    Subclassing ``ObjectView``:
    ===========================

    Just define your own method called ``get_context`` that returns a context
    dictionary for rendering a template.  The request will be rendered to
    template using ``self.template_name`` as the template that the context will
    be rendered to, so you better define that, too.

    If you find the need to redirect a user to another page from within a context
    method, simply raise the ``HttpRedirect`` exception with a string path of where
    you would like to redirect the user to, ie

        ``raise HttpRedirect("/auth/permission_denied/")``

    Defining the URLs:
    ==================

    In urls.py, you cannot simply pass the object to the url, as you would a
    function. This would mean that every request uses the same ObjectView instance,
    and in a multi-threaded environment (such as mod_wsgi) this will lead to very
    nasty bugs because of the shared namespace between different requests. That is
    why you must also import the instantiator to your project and wrap it around
    your ObjectView subclass in urls.py, ie

        ``url(r'^path/$', instantiator(ObjectView), name="object_view")``

    The instantiator will return a new instance of your class for every request,
    making it safe for multi-threading.
    """
    __metaclass__ = ObjectViewMeta

    def __call__(self, request, object=None):
        try:
            return super(ObjectView, self).__call__(request, object)
        except HttpRedirect, e:
            return e.redirect


def instantiator(cls, **kwargs):
    """
    It is possibly helpful to think of the instantiator as a decorator that
    takes a class rather than a function. Simply put, the instantiator is a
    function which takes a class and returns a new function.

    Calling the returned function will instantiate and return a new instance of
    the original class that was passed in.
    """
    def new_instance(request, object=None):
        instance = cls(**kwargs)
        return instance(request, object)
    return new_instance
