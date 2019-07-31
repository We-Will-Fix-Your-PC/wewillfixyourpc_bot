/**
 * @hidden
 */
export interface StackFrame {
    url: string;
    func: string;
    args: string[];
    line: number;
    column: number;
    context: string[];
}
/**
 * @hidden
 */
export interface StackTrace {
    /**
     * Known modes: callers, failed, multiline, onerror, stack, stacktrace
     */
    mode: string;
    mechanism: string;
    name: string;
    message: string;
    url: string;
    stack: StackFrame[];
    useragent: string;
    original?: string;
}
interface ComputeStackTrace {
    /**
     * Computes a stack trace for an exception.
     * @param {Error} ex
     * @param {(string|number)=} depth
     */
    (ex: Error, depth?: string | number): StackTrace;
}
declare const _subscribe: any;
declare const _installGlobalHandler: any;
declare const _installGlobalUnhandledRejectionHandler: any;
declare const _computeStackTrace: ComputeStackTrace;
export { _subscribe, _installGlobalHandler, _installGlobalUnhandledRejectionHandler, _computeStackTrace };
//# sourceMappingURL=tracekit.d.ts.map