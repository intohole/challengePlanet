(function() {
    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const PHONE_RE = /^1[3-9]\d{9}$/;
    const URL_RE = /^(https?:\/\/)?([\w-]+(\.[\w-]+)+)(:\d+)?(\/[^\s]*)?$/;
    const ID_CARD_RE = /^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$/;

    function _isEmpty(value) {
        if (value === null || value === undefined) return true;
        if (typeof value === 'string') return value.trim() === '';
        if (Array.isArray(value)) return value.length === 0;
        return false;
    }

    function _toStr(value) {
        if (value === null || value === undefined) return '';
        return String(value);
    }

    function required(message = '此字段必填') {
        return (value) => _isEmpty(value) ? message : '';
    }

    function requiredIf(predicate, message = '此字段必填') {
        return (value, allValues) => {
            if (!predicate(allValues, value)) return '';
            return _isEmpty(value) ? message : '';
        };
    }

    function minLength(n, message) {
        const min = Number(n);
        return (value) => {
            if (_isEmpty(value)) return '';
            const len = _toStr(value).length;
            return len < min ? (message || `至少需要${min}个字符`) : '';
        };
    }

    function maxLength(n, message) {
        const max = Number(n);
        return (value) => {
            if (_isEmpty(value)) return '';
            const len = _toStr(value).length;
            return len > max ? (message || `最多${max}个字符`) : '';
        };
    }

    function email(message = '请输入有效的邮箱地址') {
        return (value) => {
            if (_isEmpty(value)) return '';
            return EMAIL_RE.test(_toStr(value).trim()) ? '' : message;
        };
    }

    function phone(message = '请输入有效的手机号') {
        return (value) => {
            if (_isEmpty(value)) return '';
            return PHONE_RE.test(_toStr(value).trim()) ? '' : message;
        };
    }

    function url(message = '请输入有效的URL') {
        return (value) => {
            if (_isEmpty(value)) return '';
            const s = _toStr(value).trim();
            if (URL_RE.test(s)) return '';
            try { new URL(s); return ''; } catch (e) { return message; }
        };
    }

    function number(message = '请输入数字') {
        return (value) => {
            if (_isEmpty(value)) return '';
            return isNaN(Number(value)) ? message : '';
        };
    }

    function integer(message = '请输入整数') {
        return (value) => {
            if (_isEmpty(value)) return '';
            const s = _toStr(value).trim();
            return /^-?\d+$/.test(s) ? '' : message;
        };
    }

    function range(min, max, message) {
        const lo = Number(min);
        const hi = Number(max);
        return (value) => {
            if (_isEmpty(value)) return '';
            const n = Number(value);
            if (isNaN(n)) return message || `请输入 ${lo}-${hi} 之间的数字`;
            return (n < lo || n > hi) ? (message || `数值应在 ${lo}-${hi} 之间`) : '';
        };
    }

    function min(minVal, message) {
        const lo = Number(minVal);
        return (value) => {
            if (_isEmpty(value)) return '';
            const n = Number(value);
            if (isNaN(n)) return message || `不能小于 ${lo}`;
            return n < lo ? (message || `不能小于 ${lo}`) : '';
        };
    }

    function max(maxVal, message) {
        const hi = Number(maxVal);
        return (value) => {
            if (_isEmpty(value)) return '';
            const n = Number(value);
            if (isNaN(n)) return message || `不能大于 ${hi}`;
            return n > hi ? (message || `不能大于 ${hi}`) : '';
        };
    }

    function pattern(regex, message = '格式不正确') {
        const re = regex instanceof RegExp ? regex : new RegExp(regex);
        return (value) => {
            if (_isEmpty(value)) return '';
            return re.test(_toStr(value)) ? '' : message;
        };
    }

    function idCard(message = '请输入有效的身份证号') {
        return (value) => {
            if (_isEmpty(value)) return '';
            return ID_CARD_RE.test(_toStr(value).trim()) ? '' : message;
        };
    }

    function oneOf(list, message = '取值无效') {
        const arr = Array.isArray(list) ? list : [list];
        return (value) => {
            if (_isEmpty(value)) return '';
            return arr.includes(value) ? '' : message;
        };
    }

    function custom(fn, message = '校验失败') {
        return (value, allValues) => {
            if (_isEmpty(value)) return '';
            try {
                const ok = fn(value, allValues);
                if (ok instanceof Promise) {
                    return ok.then(real => real ? '' : message);
                }
                return ok ? '' : message;
            } catch (e) {
                return message;
            }
        };
    }

    function composeValidators(...validators) {
        const fns = validators.filter(Boolean);
        return (value, allValues) => {
            for (const v of fns) {
                const result = v(value, allValues);
                if (result) return result;
            }
            return '';
        };
    }

    function validateField(value, validators, allValues) {
        if (!validators) return '';
        const arr = Array.isArray(validators) ? validators : [validators];
        return composeValidators(...arr)(value, allValues);
    }

    function validateForm(form, rules) {
        const errors = {};
        const allValues = form || {};
        for (const [field, validators] of Object.entries(rules || {})) {
            if (!validators) continue;
            const err = validateField(allValues[field], validators, allValues);
            if (err) errors[field] = err;
        }
        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    }

    function validateFields(form, fields, rules) {
        const errors = {};
        const allValues = form || {};
        for (const field of fields) {
            const validators = rules && rules[field];
            if (!validators) continue;
            const err = validateField(allValues[field], validators, allValues);
            if (err) errors[field] = err;
        }
        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    }

    function makeFieldValidator(rules) {
        return (form) => validateForm(form, rules);
    }

    const NexusValidators = {
        isEmpty: _isEmpty,
        required, requiredIf,
        minLength, maxLength,
        email, phone, url,
        number, integer, range, min, max,
        pattern, idCard, oneOf, custom,
        composeValidators,
        validateField, validateForm, validateFields,
        makeFieldValidator
    };

    window.NexusValidators = NexusValidators;
})();
