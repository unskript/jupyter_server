import asyncio
import json

from anyio.to_thread import run_sync
from tornado import web

from ...base.handlers import APIHandler
from jupyter_server.auth import authorized


AUTH_RESOURCE = "nbconvert"
BYPASS_MODE = True


LOCK = asyncio.Lock()

'''
NbConvertRootHandler::get() returns the capability list of all
exporters like this: It may be good idea to cache it after the first
response was sent out.
{
  "asciidoc": {
    "output_mimetype": "text/asciidoc"
  },
  "custom": {
    "output_mimetype": ""
  },
  "html": {
    "output_mimetype": "text/html"
  },
  "latex": {
    "output_mimetype": "text/latex"
  },
  "markdown": {
    "output_mimetype": "text/markdown"
  },
  "notebook": {
    "output_mimetype": "application/json"
  },
  "pdf": {
    "output_mimetype": "application/pdf"
  },
  "python": {
    "output_mimetype": "text/x-python"
  },
  "rst": {
    "output_mimetype": "text/restructuredtext"
  },
  "script": {
    "output_mimetype": ""
  },
  "slides": {
    "output_mimetype": "text/html"
  },
  "webpdf": {
    "output_mimetype": "application/pdf"
  }
}
'''

class NbconvertRootHandler(APIHandler):
    auth_resource = AUTH_RESOURCE
    cached = False
    cap = {}

    @web.authenticated
    @authorized
    async def get(self):
        try:
            from nbconvert.exporters import base
        except ImportError as e:
            raise web.HTTPError(500, "Could not import nbconvert: %s" % e) from e
        if BYPASS_MODE == True & self.cached == True:
            res = self.cap
            self.finish(res)
        else:
            res = {}
        # Some exporters use the filesystem when instantiating, delegate that
        # to a thread so we don't block the event loop for it.
        exporters = await run_sync(base.get_export_names)
        for exporter_name in exporters:
            try:
                async with LOCK:
                    exporter_class = await run_sync(base.get_exporter, exporter_name)
            except ValueError:
                # I think the only way this will happen is if the entrypoint
                # is uninstalled while this method is running
                continue
            # XXX: According to the docs, it looks like this should be set to None
            # if the exporter shouldn't be exposed to the front-end and a friendly
            # name if it should. However, none of the built-in exports have it defined.
            # if not exporter_class.export_from_notebook:
            #    continue
            res[exporter_name] = {
                "output_mimetype": exporter_class.output_mimetype,
            }
            
        if self.cached == False:
            self.cap = json.dumps(res)
            self.cached = True

        self.finish(json.dumps(res))


default_handlers = [
    (r"/api/nbconvert", NbconvertRootHandler),
]
