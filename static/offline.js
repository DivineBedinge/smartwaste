const OFFLINE_DB_NAME = 'smartwaste-offline';
const OFFLINE_STORE = 'reports';

function offlineDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(OFFLINE_DB_NAME, 1);
        request.onupgradeneeded = () => request.result.createObjectStore(OFFLINE_STORE, { keyPath: 'clientId' });
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function saveOfflineReport(report) {
    const db = await offlineDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(OFFLINE_STORE, 'readwrite').objectStore(OFFLINE_STORE).put(report);
        request.onsuccess = resolve;
        request.onerror = () => reject(request.error);
    });
}

async function listOfflineReports() {
    const db = await offlineDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(OFFLINE_STORE).objectStore(OFFLINE_STORE).getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function deleteOfflineReport(clientId) {
    const db = await offlineDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(OFFLINE_STORE, 'readwrite').objectStore(OFFLINE_STORE).delete(clientId);
        request.onsuccess = resolve;
        request.onerror = () => reject(request.error);
    });
}

async function queueOfflineReport(file, location, description, addressText) {
    const clientId = crypto.randomUUID();
    await saveOfflineReport({
        clientId,
        photo: file,
        mimeType: file.type,
        size: file.size,
        description: description || '',
        lat: location.lat,
        lon: location.lon,
        accuracy: location.accuracy,
        capturedAt: new Date().toISOString(),
        addressText: addressText || '',
        createdAt: new Date().toISOString(),
        syncStatus: 'pending',
        attempts: 0,
        lastError: ''
    });
    renderOfflineReports();
}

async function syncOfflineReports() {
    const reports = await listOfflineReports();
    for (const report of reports) {
        if (!navigator.onLine) break;
        report.syncStatus = 'sending';
        report.attempts += 1;
        await saveOfflineReport(report);
        const formData = new FormData();
        formData.append('file', report.photo, 'offline-report');
        formData.append('client_id', report.clientId);
        formData.append('lat', report.lat);
        formData.append('lon', report.lon);
        formData.append('description', report.description);
        formData.append('address_text', report.addressText);
        try {
            const response = await fetch('/api/v1/signalements', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: formData });
            if (response.status === 401 || response.status === 403) {
                report.syncStatus = 'auth_required';
                report.lastError = 'Authentification requise';
                await saveOfflineReport(report);
                continue;
            }
            if (!response.ok) throw new Error((await response.json()).detail || 'Erreur serveur');
            await deleteOfflineReport(report.clientId);
        } catch (error) {
            report.syncStatus = 'failed';
            report.lastError = error.message;
            await saveOfflineReport(report);
        }
    }
    renderOfflineReports();
}

async function renderOfflineReports() {
    const container = document.getElementById('offlineReportsList');
    if (!container) return;
    const reports = await listOfflineReports();
    container.replaceChildren(...reports.map(report => {
        const item = document.createElement('article');
        item.className = 'bg-white rounded-lg p-3 border border-gray-200';
        item.textContent = `${new Date(report.createdAt).toLocaleString()} - ${report.syncStatus}${report.lastError ? ` (${report.lastError})` : ''}`;
        return item;
    }));
    if (!reports.length) container.textContent = 'Aucun signalement local en attente.';
}

window.queueOfflineReport = queueOfflineReport;
window.syncOfflineReports = syncOfflineReports;
window.renderOfflineReports = renderOfflineReports;