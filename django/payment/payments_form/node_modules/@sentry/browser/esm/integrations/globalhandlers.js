import * as tslib_1 from "tslib";
import { getCurrentHub } from '@sentry/core';
import { addExceptionTypeValue, isString, logger, normalize, truncate } from '@sentry/utils';
import { shouldIgnoreOnError } from '../helpers';
import { eventFromStacktrace } from '../parsers';
import { _installGlobalHandler, _installGlobalUnhandledRejectionHandler, _subscribe, } from '../tracekit';
/** Global handlers */
var GlobalHandlers = /** @class */ (function () {
    /** JSDoc */
    function GlobalHandlers(options) {
        /**
         * @inheritDoc
         */
        this.name = GlobalHandlers.id;
        this._options = tslib_1.__assign({ onerror: true, onunhandledrejection: true }, options);
    }
    /**
     * @inheritDoc
     */
    GlobalHandlers.prototype.setupOnce = function () {
        Error.stackTraceLimit = 50;
        _subscribe(function (stack, _, error) {
            // TODO: use stack.context to get a valuable information from TraceKit, eg.
            // [
            //   0: "  })"
            //   1: ""
            //   2: "  function foo () {"
            //   3: "    Sentry.captureException('some error')"
            //   4: "    Sentry.captureMessage('some message')"
            //   5: "    throw 'foo'"
            //   6: "  }"
            //   7: ""
            //   8: "  function bar () {"
            //   9: "    foo();"
            //   10: "  }"
            // ]
            if (shouldIgnoreOnError()) {
                return;
            }
            var self = getCurrentHub().getIntegration(GlobalHandlers);
            if (self) {
                getCurrentHub().captureEvent(self._eventFromGlobalHandler(stack), {
                    data: { stack: stack },
                    originalException: error,
                });
            }
        });
        if (this._options.onerror) {
            logger.log('Global Handler attached: onerror');
            _installGlobalHandler();
        }
        if (this._options.onunhandledrejection) {
            logger.log('Global Handler attached: onunhandledrejection');
            _installGlobalUnhandledRejectionHandler();
        }
    };
    /**
     * This function creates an Event from an TraceKitStackTrace.
     *
     * @param stacktrace TraceKitStackTrace to be converted to an Event.
     */
    GlobalHandlers.prototype._eventFromGlobalHandler = function (stacktrace) {
        if (!isString(stacktrace.message) && stacktrace.mechanism !== 'onunhandledrejection') {
            // There are cases where stacktrace.message is an Event object
            // https://github.com/getsentry/sentry-javascript/issues/1949
            // In this specific case we try to extract stacktrace.message.error.message
            var message = stacktrace.message;
            stacktrace.message =
                message.error && isString(message.error.message) ? message.error.message : 'No error message';
        }
        var event = eventFromStacktrace(stacktrace);
        var data = {
            mode: stacktrace.mode,
        };
        if (stacktrace.message) {
            data.message = stacktrace.message;
        }
        if (stacktrace.name) {
            data.name = stacktrace.name;
        }
        var client = getCurrentHub().getClient();
        var maxValueLength = (client && client.getOptions().maxValueLength) || 250;
        var fallbackValue = stacktrace.original
            ? truncate(JSON.stringify(normalize(stacktrace.original)), maxValueLength)
            : '';
        var fallbackType = stacktrace.mechanism === 'onunhandledrejection' ? 'UnhandledRejection' : 'Error';
        // This makes sure we have type/value in every exception
        addExceptionTypeValue(event, fallbackValue, fallbackType, {
            data: data,
            handled: false,
            type: stacktrace.mechanism,
        });
        return event;
    };
    /**
     * @inheritDoc
     */
    GlobalHandlers.id = 'GlobalHandlers';
    return GlobalHandlers;
}());
export { GlobalHandlers };
//# sourceMappingURL=globalhandlers.js.map