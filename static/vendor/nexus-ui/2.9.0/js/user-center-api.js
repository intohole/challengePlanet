(function() {
if (!window.UserCenterSDK) {
    console.error('UserCenterSDK not loaded. Load user-center-sdk.js before user-center-api.js');
    return;
}

const SDK = window.UserCenterSDK;
const P = SDK.prototype;

P.getUserPermissions = function() {
    return this._request('GET', '/api/users/permissions');
};

P.getUsers = function(skip = 0, limit = 100) {
    return this._request('GET', `/api/users?skip=${skip}&limit=${limit}`);
};

P.getUser = function(userId) {
    return this._request('GET', `/api/users/${userId}`);
};

P.updateUser = function(userId, updateData) {
    return this._request('PUT', `/api/users/${userId}`, updateData);
};

P.deleteUser = function(userId) {
    return this._request('DELETE', `/api/users/${userId}`);
};

P.getDashboardStats = function() {
    return this._request('GET', '/api/users/stats');
};

P.getApplications = function(skip = 0, limit = 100) {
    return this._request('GET', `/api/applications?skip=${skip}&limit=${limit}`);
};

P.getApplication = function(appId) {
    return this._request('GET', `/api/applications/${appId}`);
};

P.createApplication = function(appData) {
    return this._request('POST', '/api/applications', appData);
};

P.updateApplication = function(appId, appData) {
    return this._request('PUT', `/api/applications/${appId}`, appData);
};

P.deleteApplication = function(appId) {
    return this._request('DELETE', `/api/applications/${appId}`);
};

P.getRoles = function(skip = 0, limit = 100) {
    return this._request('GET', `/api/permissions/roles?skip=${skip}&limit=${limit}`);
};

P.createRole = function(name, description = null) {
    return this._request('POST', '/api/permissions/roles', { name, description });
};

P.getPermissions = function(skip = 0, limit = 100) {
    return this._request('GET', `/api/permissions?skip=${skip}&limit=${limit}`);
};

P.createPermission = function(name, code, description = null) {
    return this._request('POST', '/api/permissions', { name, code, description });
};

P.validateInviteCode = function(code, appKey = null) {
    return this._request('POST', '/api/invite-codes/validate', {
        code,
        app_key: appKey || this.appKey
    }, false);
};

P.useInviteCode = function(inviteCode) {
    return this._request('POST', '/api/invite-codes/use', { invite_code: inviteCode });
};

P.createInviteCodeBatch = function(appId, batchName, totalCount = 10, options = {}) {
    const data = { app_id: appId, batch_name: batchName, total_count: totalCount, ...options };
    return this._request('POST', '/api/invite-codes/batch', data);
};

P.getInviteCodeBatches = function(appId = null) {
    const path = appId ? `/api/invite-codes/batch?app_id=${appId}` : '/api/invite-codes/batch';
    return this._request('GET', path);
};

P.getDiscovery = function() {
    return this._request('GET', '/api/discovery');
};

P.getIntegrationGuide = function() {
    return this._request('GET', '/api/discovery/integration-guide');
};

P.getVipLevels = function() {
    return this._request('GET', `/api/vip/levels?app_key=${this.appKey}`);
};

P.upgradeVip = function(levelCode, durationDays = null) {
    const data = { level_code: levelCode };
    if (durationDays) data.duration_days = durationDays;
    return this._request('POST', '/api/vip/upgrade', data);
};

P.checkVipExpiry = function() {
    return this._request('GET', '/api/vip/check-expiry');
};

window.UserCenterAPI = { loaded: true };
})();
