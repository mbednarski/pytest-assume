import inspect
import os.path

import pytest

try:
    from py.io import saferepr
except ImportError:
    saferepr = repr

_FAILED_ASSUMPTIONS = []
_ASSUMPTION_LOCALS = []


def assume(expr, msg=''):
    """
    Checks the expression, if it's false, add it to the
    list of failed assumptions. Also, add the locals at each failed
    assumption, if showlocals is set.

    :param expr: Expression to 'assert' on.
    :param msg: Message to display if the assertion fails.
    :return: None
    """
    if not expr:
        (frame, filename, line, funcname, contextlist) = inspect.stack()[1][0:5]
        # get filename, line, and context
        filename = os.path.relpath(filename)
        context = contextlist[0].lstrip() if not msg else msg
        # format entry
        entry = u"{filename}:{line}: AssumptionFailure\n\t{context}".format(**locals())
        # add entry
        _FAILED_ASSUMPTIONS.append(entry)
        if getattr(pytest, "_showlocals", None):
            # Debatable whether we should display locals for
            # every failed assertion, or just the final one.
            # I'm defaulting to per-assumption, just because vars
            # can easily change between assumptions.
            pretty_locals = ["%-10s = %s" % (name, saferepr(val))
                             for name, val in frame.f_locals.items()]
            _ASSUMPTION_LOCALS.append(pretty_locals)


def pytest_configure(config):
    """
    Add tracking lists to the pytest namespace, so we can
    always access it, as well as the 'assume' function itself.

    :return: Dictionary of name: values added to the pytest namespace.
    """
    pytest.assume = assume
    pytest._showlocals = config.getoption("showlocals")


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_makereport(item, call):
    """
    Check if the test failed, if it didn't fail, and there are
    failed assumptions, fail the test & output the assumptions as the longrepr.

    If the test already failed, then just add in failed assumptions to a new section
    in the longrepr.

    :param item:
    :param call:
    :return:
    """
    outcome = yield
    report = outcome.get_result()
    failed_assumptions = _FAILED_ASSUMPTIONS
    assumption_locals = _ASSUMPTION_LOCALS
    evalxfail = getattr(item, '_evalxfail', None)
    if call.when == "call" and failed_assumptions:
        if evalxfail and evalxfail.wasvalid() and evalxfail.istrue():
            report.outcome = "skipped"
            report.wasxfail = evalxfail.getexplanation()
        else:
            summary = 'Failed Assumptions: %s' % len(failed_assumptions)
            if report.longrepr:
                # Do we want to have the locals displayed here as well?
                # I'd say no, because the longrepr would already be displaying locals.
                report.sections.append((summary, "\n".join(failed_assumptions)))
            else:
                if assumption_locals:
                    assume_data = zip(failed_assumptions, assumption_locals)
                    longrepr = ["{0}\n{1}\n\n".format(assumption, "\n".join(flocals))
                                for assumption, flocals in assume_data]
                else:
                    longrepr = ["\n\n".join(failed_assumptions)]
                longrepr.append("-" * 60)
                longrepr.append(summary)
                report.longrepr = '\n'.join(longrepr)
            report.outcome = "failed"

    if _FAILED_ASSUMPTIONS:
        del _FAILED_ASSUMPTIONS[:]
    if _ASSUMPTION_LOCALS:
        del _ASSUMPTION_LOCALS[:]
