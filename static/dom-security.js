(function (global) {
    'use strict';

    class SafeHtml {
        constructor(value) { this.value = value; }
        toString() { return this.value; }
    }

    const escapeText = value => value instanceof SafeHtml ? value.value : String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');

    function safeHtml(strings, ...values) {
        return new SafeHtml(strings.reduce((result, part, index) =>
            result + part + (index < values.length ? escapeText(values[index]) : ''), ''));
    }

    function safeUrl(value, options = {}) {
        const allowed = new Set(options.protocols || ['https:', 'tel:']);
        if (options.allowHttpOnLocalhost && ['localhost', '127.0.0.1'].includes(location.hostname)) {
            allowed.add('http:');
        }
        try {
            const url = new URL(String(value), location.origin);
            return allowed.has(url.protocol) ? url.href : null;
        } catch (_) {
            return null;
        }
    }

    function safeImageDataUrl(value) {
        const text = String(value || '');
        return /^data:image\/(?:png|jpeg|webp);base64,[a-z0-9+/=\r\n]+$/i.test(text) ? text : null;
    }

    global.escapeText = escapeText;
    global.safeHtml = safeHtml;
    global.safeUrl = safeUrl;
    global.safeImageDataUrl = safeImageDataUrl;
})(window);
