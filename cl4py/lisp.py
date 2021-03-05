import subprocess
import io
import os.path
import urllib.request
import tempfile
from pkg_resources import resource_filename
from .data import *
from .reader import Readtable
from .writer import lispify
import logging
import sys

logging.basicConfig(level=logging.DEBUG)
class Lisp:
    def __init__(self, cmd=['sbcl', '--script'], quicklisp=False, debug=False):
        p = subprocess.Popen(cmd + [resource_filename(__name__, 'py.lisp')],
                             stdin = subprocess.PIPE,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE,
                             shell = False)
        self.stdin = io.TextIOWrapper(p.stdin, write_through=True,
                                      line_buffering=1,
                                      encoding='utf-8')
        self.stdout = io.TextIOWrapper(p.stdout, encoding='utf-8')
        # The name of the current package.
        self.package = "COMMON-LISP-USER"
        # Each Lisp process has its own readtable.
        self.readtable = Readtable(self)
        # The classes dict maps from symbols to python classes.
        self.classes = {}
        # Whenever the reader encounters a Lisp object whose class is not
        # yet known, it stores it in this {class_name : instances} dict.
        # This allows us to patch these instances later.
        self.unpatched_instances = {}
        # If debug is true, cl4py will print plenty of debug information.
        self.debug = debug
        # Finally, check whether the user wants quicklisp to be available.
        logging.info("Created new Lisp instance:\ncmd: {}\nquicklisp: {}\ndebug: {}".format(cmd, quicklisp, debug))
        if quicklisp:
            logging.info("Installing QuickLisp...")
            install_and_load_quicklisp(self)
            logging.info("QuickLisp installed.")


    def __del__(self):
        try:
            logging.info("Deleting instance...")
            self.stdin.write('(cl-user:quit)\n')
            logging.info("Instance deleted")
        except:
            logging.debug("Instance deletion failed.")
            logging.debug(sys.exc_info()[0])
            # pass


    def eval(self, expr):
        sexp = lispify(self, expr)
        if self.debug: print(sexp)
        self.stdin.write(sexp + '\n')
        pkg = self.readtable.read(self.stdout)
        val = self.readtable.read(self.stdout)
        err = self.readtable.read(self.stdout)
        msg = self.readtable.read(self.stdout)
        # Update the current package.
        self.package = pkg
        # Write the Lisp output to the Python output.
        print(msg,end='')
        # If there is an error, raise it.
        if isinstance(err, Cons):
            condition = err.car
            msg = err.cdr.car if err.cdr else ""
            logging.debug("Error being raised in lisp.py/eval.\nerr = {}\ncondition = {}\nmsg = {}".format(err, condition, msg))
            def init(self):
                RuntimeError.__init__(self, msg)
            raise type(str(condition), (RuntimeError,),
                       {'__init__': init})()
        # Now, check whether there are any unpatched instances.  If so,
        # figure out their class definitions and patch them accordingly.
        items = list(self.unpatched_instances.items())
        self.unpatched_instances.clear()
        for (cls_name, instances) in items:
            cls = type(cls_name.python_name, (LispWrapper,), {})
            self.classes[cls_name] = cls
            alist = self.function('cl4py:class-information')(cls_name)
            logging.info("Adding member functions for {}".format(cls_name))
            for cons in alist:
                add_member_function(cls, cons.car, cons.cdr)
            for instance in instances:
                logging.info("Patching {} with class {}".format(instance, cls_name))
                instance.__class__ = cls
        # Finally, return the resulting values.
        if val == ():
            logging.info("{} returns None".format(expr))
            return None
        elif val.cdr == ():
            logging.info("{} returns {}".format(expr, val.car))
            return val.car
        else:
            ret = tuple(val)
            logging.info("{} returns {}".format(expr, ret))
            return ret


    def find_package(self, name):
        logging.info("Finding package {}".format(name))
        return self.function('CL:FIND-PACKAGE')(name)
        # logging.info("Package {} Found: {}".format(name, p))
        # return p


    def function(self, name):
        logging.info("Evaluating {}".format(name))
        e = self.eval( ('CL:FUNCTION', name) )
        logging.info("Evaluated {} Found {}".format(name, e))
        return e


def add_member_function(cls, name, gf):
    class_name = cls.__name__
    method_name = name.python_name
    logging.info("Adding member function. Method {}, Class {}".format(method_name, class_name))
    setattr(cls, method_name, lambda self, *args: gf(self, *args))


def install_and_load_quicklisp(lisp):
    logging.info("Installing QuickLisp")
    quicklisp_setup = os.path.expanduser('~/quicklisp/setup.lisp')
    if os.path.isfile(quicklisp_setup):
        lisp.function('cl:load')(quicklisp_setup)
        logging.info("QuickLisp found already and loaded.")
    else:
        logging.info("Installing from outside.")
        install_quicklisp(lisp)


def install_quicklisp(lisp):
    import urllib
    url = 'https://beta.quicklisp.org/quicklisp.lisp'
    with tempfile.NamedTemporaryFile(prefix='quicklisp-', suffix='.lisp') as tmp:
        with urllib.request.urlopen(url) as u:
            tmp.write(u.read())
        lisp.function('cl:load')(tmp.name)
    print('Installing Quicklisp...')
    lisp.eval( ('quicklisp-quickstart:install',) )
    logging.info("QuickLisp installed from outside.")
