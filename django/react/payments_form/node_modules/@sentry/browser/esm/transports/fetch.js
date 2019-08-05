import * as tslib_1 from "tslib";
import { Status } from '@sentry/types';
import { getGlobalObject, supportsReferrerPolicy } from '@sentry/utils';
import { BaseTransport } from './base';
var global = getGlobalObject();
/** `fetch` based transport */
var FetchTransport = /** @class */ (function (_super) {
    tslib_1.__extends(FetchTransport, _super);
    function FetchTransport() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    /**
     * @inheritDoc
     */
    FetchTransport.prototype.sendEvent = function (event) {
        var defaultOptions = {
            body: JSON.stringify(event),
            method: 'POST',
            // Despite all stars in the sky saying that Edge supports old draft syntax, aka 'never', 'always', 'origin' and 'default
            // https://caniuse.com/#feat=referrer-policy
            // It doesn't. And it throw exception instead of ignoring this parameter...
            // REF: https://github.com/getsentry/raven-js/issues/1233
            referrerPolicy: (supportsReferrerPolicy() ? 'origin' : ''),
        };
        return this._buffer.add(global.fetch(this.url, defaultOptions).then(function (response) { return ({
            status: Status.fromHttpCode(response.status),
        }); }));
    };
    return FetchTransport;
}(BaseTransport));
export { FetchTransport };
//# sourceMappingURL=fetch.js.map