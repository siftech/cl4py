import os
import json
from pytest import fixture
import cl4py


# pytest forces violation of this pylint rule
# pylint: disable=redefined-outer-name


@fixture(scope="module")
def lisp():
    return cl4py.Lisp()


@fixture(scope="module")
def cl(lisp):
    return lisp.function("find-package")("CL")


# This test verifies issue underlying MR #9, where
# the readtable variable of the lisp process was bound with
# too wide a scope, breaking reading of arbitrary things.
def test_readtable_problem(cl):
    retval = cl.compile_file(
        os.path.join(os.path.dirname(__file__), "sample-program.lisp")
    )
    outfile = os.path.join(os.path.dirname(__file__), "sample-program.fasl")
    try:
        assert retval[0] == outfile
        assert os.path.exists(retval[0])
        assert retval[1] == ()
        assert retval[2] == ()
    finally:
        cleanup(outfile)
    cleanup(outfile)

def cleanup(outfile):
    if os.path.exists(outfile):
        try:
            os.remove(outfile)
        except:                 # pylint: disable=bare-except
            pass


def test_json_boolean_problem(cl):
    retval = cl.load(
        os.path.join(os.path.dirname(__file__), "sample-json-output.lisp")
    )
    assert retval
    # foo = cl_user.status
    json_string = cl.eval(cl4py.Symbol('STATUS', "COMMON-LISP-USER"))
    print(json_string)
    js = json.loads(json_string)
    assert js['flag'] == True # pylint: disable=singleton-comparison
