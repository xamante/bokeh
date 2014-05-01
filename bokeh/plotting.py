from __future__ import print_function

from functools import wraps
import itertools
import logging
import os
import uuid
import warnings

from . import browserlib
from . import _glyph_functions
from .document import Document
from .objects import Axis, Grid, GridPlot, Legend
from .palettes import brewer
from .plotting_helpers import (
    get_default_color, get_default_alpha, _handle_1d_data_args, _list_attr_splat
)
from .protocol import serialize_json
from .resources import Resources
from .session import Cloud, DEFAULT_SERVER_URL, Session
from .templates import FILE, NOTEBOOK_DIV, PLOT_DIV, PLOT_JS, PLOT_SCRIPT, RESOURCES

logger = logging.getLogger(__name__)

_default_document = Document()

_default_session = None

_default_file = None

_default_notebook = None

def curdoc():
    ''' Return the current document.

    Returns:
        doc : the current default document object.
    '''
    try:
        from flask import request
        doc = request.bokeh_server_document
        logger.debug("returning config from flask request")
        return doc
    except (ImportError, RuntimeError, AttributeError):
        logger.debug("returning global config from bokeh.plotting")
        return _default_document

def curplot():
    ''' Return the current default plot object.

    Returns:
        plot : the current default plot (or None)
    '''
    return curdoc().curplot()

def cursession():
    ''' Return the current session, if there is one.

    Returns:
        session : the current default session object (or None)
    '''
    return _default_session

def push(session=None, document=None):
    if not session:
        session = cursession()
    if not document:
        document = curdoc()
    return session.push_dirty(document)

def hold(value=True):
    ''' Set or clear the plot hold status on the current document.

    This is a convenience function that acts on the current document, and is equivalent to curdoc().hold(...)

    Args:
        value (bool, optional) : whether hold should be turned on or off (default: True)

    Returns:
        None
    '''
    curdoc().hold(value)

def figure(**kwargs):
    ''' Activate a new figure for plotting.

    All subsequent plotting operations will affect the new figure.

    This function accepts all plot style keyword parameters.

    Returns:
        None

    '''
    curdoc().figure(**kwargs)

def output_server(docname, session=None, url="default", name=None):
    """ Cause plotting commands to automatically persist plots to a Bokeh server.

    Can use explicitly provided Session for persistence, or the default
    session.

    Args:
        docname (str) : name of document to push on Bokeh server
            An existing documents with the same name will be overwritten.
        session (Session, optional) : An explicit session to use (default: None)
            If session is None, use the default session
        url (str, optianal) : URL of the Bokeh server  (default: "default")
            if url is "default" use session.DEFAULT_SERVER_URL
        name (str, optional) :
            if name is None, use the server URL as the name

    Additional keyword arguments like **username**, **userapikey**,
    and **base_url** can also be supplied.

    Returns:
        None

    .. note:: Generally, this should be called at the beginning of an
              interactive session or the top of a script.

    .. note:: Calling this function will replaces any existing default Server session

    """
    global _default_session
    if url == "default":
        url = DEFAULT_SERVER_URL
    if name is None:
        name = url
    if not session:
        if not _default_session:
            _default_session = Session(name=name, root_url=url)
        session = _default_session
    session.use_doc(docname)
    session.pull_document(curdoc())

def output_cloud(docname):
    """ Cause plotting commands to automatically persist plots to the Bokeh
    cloud server.

    Args:
        docname (str) : name of document to push on Bokeh server
            An existing documents with the same name will be overwritten.

    .. note:: Generally, this should be called at the beginning of an
              interactive session or the top of a script.

    .. note:: Calling this function will replaces any existing default Server session

    """
    output_server(docname, session=Cloud())

def output_notebook():
    from . import load_notebook
    load_notebook()
    global _default_notebook
    _default_notebook = True

def output_file(filename, title="Bokeh Plot", autosave=True, mode="inline", rootdir=None):
    """ Outputs to a static HTML file.

    .. note:: This file will be overwritten each time show() or save() is invoked.

    Args:
        autosave (bool, optional) : whether to automatically save (default: True)
            If **autosave** is True, then every time plot() or one of the other
            visual functions is called, this causes the file to be saved. If it
            is False, then the file is only saved upon calling show().

        mode (str, optional) : how to inlude BokehJS (default: "inline")
            **mode** can be 'inline', 'cdn', 'relative(-dev)' or 'absolute(-dev)'.
            In the 'relative(-dev)' case, **rootdir** can be specified to indicate the
            base directory from which the path to the various static files should be
            computed.

    .. note:: Generally, this should be called at the beginning of an
              interactive session or the top of a script.

    """
    global _default_file
    _default_file = {
        'filename'  : filename,
        'resources' : Resources(mode='inline', rootdir=rootdir, minified=False),
        'autosave'  : autosave,
        'title'     : title,
    }

    if os.path.isfile(filename):
        print("Session output file '%s' already exists, will be overwritten." % filename)


def _notebook_div():
    plot_ref = curplot().get_ref()
    elementid = str(uuid.uuid4())
    plot_js = PLOT_JS.render(
        elementid = elementid,
        modelid = plot_ref["id"],
        modeltype = plot_ref["type"],
        all_models = serialize_json(curdoc().dump())
    )
    plot_script = PLOT_SCRIPT.render(
        plot_js = plot_js,
    )
    plot_div = PLOT_DIV.render(elementid=elementid)
    html = NOTEBOOK_DIV.render(
        plot_script = plot_script,
        plot_div = plot_div,
    )
    return html.encode("utf-8")

def show(browser=None, new="tab", url=None):
    """ 'shows' the current plot, by auto-raising the window or tab
    displaying the current plot (for file/server output modes) or displaying
    it in an output cell (IPython notebook).

    Args:
        browser (str, optional) : browser to show with (default: None)
            For systems that support it, the **browser** argument allows specifying
            which browser to display in, e.g. "safari", "firefox", "opera",
            "windows-default".  (See the webbrowser module documentation in the
            standard lib for more details.)

        new (str, optional) : new file output mode (default: "tab")
            For file-based output, opens or raises the browser window
            showing the current output file.  If **new** is 'tab', then
            opens a new tab. If **new** is 'window', then opens a new window.
    """
    filename = _default_file['filename'] if _default_file else None
    session = cursession()
    notebook = _default_notebook

    # Map our string argument to the webbrowser.open argument
    new_param = {'tab': 2, 'window': 1}[new]

    controller = browserlib.get_browser_controller(browser=browser)

    if notebook and session:
        push(session=session)
        # show in notebook

    elif notebook:
        import IPython.core.displaypub as displaypub
        displaypub.publish_display_data('bokeh', {'text/html': _notebook_div()})

    elif session:
        push()
        if url:
            controller.open(url, new=new_param)
        else:
            controller.open(session.object_link(curdoc()._plotcontext))

    elif filename:
        save(filename)
        controller.open("file://" + os.path.abspath(filename), new=new_param)

def _file_html(resources, title):
    context_ref = curdoc().get_context_ref()
    elementid = str(uuid.uuid4())
    plot_resources = RESOURCES.render(
        js_raw = resources.js_raw,
        css_raw = resources.css_raw,
        js_files = resources.js_files,
        css_files = resources.css_files,
    )
    plot_js = PLOT_JS.render(
        elementid = elementid,
        modelid = context_ref["id"],
        modeltype = context_ref["type"],
        all_models = serialize_json(curdoc().dump()),
    )
    plot_script = PLOT_SCRIPT.render(
        plot_js = resources.js_wrapper(plot_js),
    )
    plot_div = PLOT_DIV.render(elementid=elementid)
    html = FILE.render(
        title = title,
        plot_resources = plot_resources,
        plot_script = plot_script,
        plot_div = plot_div,
    )
    return html.encode("utf-8")

def save(filename=None, resources=None):
    """ Updates the file with the data for the current document.

    If a filename is supplied, or output_file(...) has been called, this will
    save the plot to the given filename.

    Args:
        filename (str, optional) : filename to save document under (default: None)
            if `filename` is None, the current output_file(...) filename is used if present
        resources (Resources, optional) : BokehJS resource config to use
            if `resources` is None, the current default resource config is used
    """
    if filename is None and _default_file:
        filename = _default_file['filename']

    if resources is None and _default_file:
        resources = _default_file['resources']

    if not filename:
        warnings.warn("save() called but no filename was supplied and output_file(...) was never called, nothing saved")
        return
    if not resources:
        warnings.warn("save() called but no resources was supplied and output_file(...) was never called, nothing saved")
        return

    html = _file_html(resources, _default_file['title'])
    with open(filename, "w") as f:
        f.write(html)

def push(session=None, document=None):
    if not session:
        session = cursession()
    if not document:
        document = curdoc()
    if session:
        return session.push_dirty(curdoc())
    else:
        warnings.warn("push() called but no session was supplied and output_server(...) was never called, nothing pushd")
        
def _document_wrap(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        retval = func(curdoc(), *args, **kwargs)
        if cursession() and curdoc()._autostore:
            push()
        if _default_file and _default_file['autosave']:
            save()
        return retval
    wrapper.__doc__ += "\nThis is a convenience function that acts on the current document, and is equivalent to curdoc().%s(...)" % func.__name__
    return wrapper


annular_wedge     = _document_wrap(_glyph_functions.annular_wedge)
annulus           = _document_wrap(_glyph_functions.annulus)
arc               = _document_wrap(_glyph_functions.arc)
asterisk          = _document_wrap(_glyph_functions.asterisk)
bezier            = _document_wrap(_glyph_functions.bezier)
circle            = _document_wrap(_glyph_functions.circle)
circle_cross      = _document_wrap(_glyph_functions.circle_cross)
circle_x          = _document_wrap(_glyph_functions.circle_x)
cross             = _document_wrap(_glyph_functions.cross)
diamond           = _document_wrap(_glyph_functions.diamond)
diamond_cross     = _document_wrap(_glyph_functions.diamond_cross)
image             = _document_wrap(_glyph_functions.image)
image_rgba        = _document_wrap(_glyph_functions.image_rgba)
image_url         = _document_wrap(_glyph_functions.image_url)
inverted_triangle = _document_wrap(_glyph_functions.inverted_triangle)
line              = _document_wrap(_glyph_functions.line)
multi_line        = _document_wrap(_glyph_functions.multi_line)
oval              = _document_wrap(_glyph_functions.oval)
patch             = _document_wrap(_glyph_functions.patch)
patches           = _document_wrap(_glyph_functions.patches)
quad              = _document_wrap(_glyph_functions.quad)
quadratic         = _document_wrap(_glyph_functions.quadratic)
ray               = _document_wrap(_glyph_functions.ray)
rect              = _document_wrap(_glyph_functions.rect)
segment           = _document_wrap(_glyph_functions.segment)
square            = _document_wrap(_glyph_functions.square)
square_cross      = _document_wrap(_glyph_functions.square_cross)
square_x          = _document_wrap(_glyph_functions.square_x)
text              = _document_wrap(_glyph_functions.text)
triangle          = _document_wrap(_glyph_functions.triangle)
wedge             = _document_wrap(_glyph_functions.wedge)
x                 = _document_wrap(_glyph_functions.x)

_marker_types = {
    "asterisk": asterisk,
    "circle": circle,
    "circle_cross": circle_cross,
    "circle_x": circle_x,
    "cross": cross,
    "diamond": diamond,
    "diamond_cross": diamond_cross,
    "inverted_triangle": inverted_triangle,
    "square": square,
    "square_x": square_x,
    "square_cross": square_cross,
    "triangle": triangle,
    "x": x,
    "*": asterisk,
    "+": cross,
    "o": circle,
    "ox": circle_x,
    "o+": circle_cross,
}

def markers():
    """ Prints a list of valid marker types for scatter()

    Returns:
        None
    """
    print(list(sorted(_marker_types.keys())))


_color_fields = set(["color", "fill_color", "line_color"])
_alpha_fields = set(["alpha", "fill_alpha", "line_alpha"])

def scatter(*args, **kwargs):
    """ Creates a scatter plot of the given x and y items.

    Args:
        *args : The data to plot.  Can be of several forms:

            (X, Y)
                Two 1D arrays or iterables
            (XNAME, YNAME)
                Two bokeh DataSource/ColumnsRef

        marker (str, optional): a valid marker_type, defaults to "circle"
        color (color value, optional): shorthand to set both fill and line color

    All the :ref:`userguide_line_properties` and :ref:`userguide_fill_properties` are
    also accepted as keyword parameters.

    Examples:

        >>> scatter([1,2,3],[4,5,6], fill_color="red")
        >>> scatter("data1", "data2", source=data_source, ...)

    """
    ds = kwargs.get("source", None)
    names, datasource = _handle_1d_data_args(args, datasource=ds)
    kwargs["source"] = datasource

    markertype = kwargs.get("marker", "circle")

    # TODO: How to handle this? Just call curplot()?
    if not len(_color_fields.intersection(set(kwargs.keys()))):
        kwargs['color'] = get_default_color()
    if not len(_alpha_fields.intersection(set(kwargs.keys()))):
        kwargs['alpha'] = get_default_alpha()

    if markertype not in _marker_types:
        raise ValueError("Invalid marker type '%s'. Use markers() to see a list of valid marker types." % markertype)
    return _marker_types[markertype](*args, **kwargs)

def gridplot(plot_arrangement, name=None):
    """ Generate a plot that arranges several subplots into a grid.

    Args:
        plot_arrangement (list[:class:`Plot <bokeh.objects.Plot>`]) : plots to arrange in a grid
        name (str) : name for this plot

    .. note:: `plot_arrangement` can be nested, e.g [[p1, p2], [p3, p4]]

    Returns:
        grid_plot: the current :class:`GridPlot <bokeh.objects.GridPlot>`
    """
    grid = GridPlot(children=plot_arrangement)
    if name:
        grid._id = name
    # Walk the plot_arrangement and remove them from the plotcontext,
    # so they don't show up twice
    subplots = itertools.chain.from_iterable(plot_arrangement)
    curdoc().get_context().children = list(set(curdoc().get_context().children) - set(subplots))
    curdoc().add(grid)

    if _default_session:
        push()
    if _default_file and _default_file['autosave']:
        save()

def xaxis():
    """ Get the current axis objects

    Returns:
        Returns axis object or splattable list of axis objects on the current plot
    """
    p = curplot()
    if p is None:
        return None
    axis = [obj for obj in p.renderers if isinstance(obj, Axis) and obj.dimension==0]
    return _list_attr_splat(axis)

def yaxis():
    """ Get the current `y` axis object(s)

    Returns:
        Returns y-axis object or splattable list of y-axis objects on the current plot
    """
    p = curplot()
    if p is None:
        return None
    axis = [obj for obj in p.renderers if isinstance(obj, Axis) and obj.dimension==1]
    return _list_attr_splat(axis)

def axis():
    """ Get the current `x` axis object(s)

    Returns:
        Returns x-axis object or splattable list of x-axis objects on the current plot
    """
    return _list_attr_splat(xaxis() + yaxis())

def legend():
    """ Get the current :class:`legend <bokeh.objects.Legend>` object(s)

    Returns:
        Returns legend object or splattable list of legend objects on the current plot
    """
    p = curplot()
    if p is None:
        return None
    legends = [obj for obj in p.renderers if isinstance(obj, Legend)]
    return _list_attr_splat(legends)

def xgrid():
    """ Get the current `x` :class:`grid <bokeh.objects.Grid>` object(s)

    Returns:
        Returns legend object or splattable list of legend objects on the current plot
    """
    p = curplot()
    if p is None:
        return None
    grid = [obj for obj in p.renderers if isinstance(obj, Grid) and obj.dimension==0]
    return _list_attr_splat(grid)

def ygrid():
    """ Get the current `y` :class:`grid <bokeh.objects.Grid>` object(s)

    Returns:
        Returns y-grid object or splattable list of y-grid objects on the current plot
    """
    p = curplot()
    if p is None:
        return None
    grid = [obj for obj in p.renderers if isinstance(obj, Grid) and obj.dimension==1]
    return _list_attr_splat(grid)

def grid():
    """ Get the current :class:`grid <bokeh.objects.Grid>` object(s)

    Returns:
        Returns grid object or splattable list of grid objects on the current plot
    """
    return _list_attr_splat(xgrid() + ygrid())

