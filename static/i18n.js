const translations = {
    fr: {
        online: 'En ligne', offline: 'Hors connexion', sync: 'Synchroniser maintenant',
        pendingReports: 'Signalements en attente', noPendingReports: 'Aucun signalement local en attente.',
        login: 'Se connecter', language: 'Langue', saved: 'Préférence enregistrée'
    },
    en: {
        online: 'Online', offline: 'Offline', sync: 'Sync now',
        pendingReports: 'Pending reports', noPendingReports: 'No local reports pending.',
        login: 'Sign in', language: 'Language', saved: 'Preference saved'
    }
};

function translatePage(language) {
    const selected = translations[language] || translations.fr;
    document.documentElement.lang = translations[language] ? language : 'fr';
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const value = selected[element.dataset.i18n] || translations.fr[element.dataset.i18n];
        if (value) element.textContent = value;
    });
    localStorage.setItem('language_preference', document.documentElement.lang);
}

async function persistLanguage(language, token) {
    translatePage(language);
    if (!token) return;
    await fetch('/api/v1/auth/me/language', {
        method: 'PATCH', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
        body: JSON.stringify({language_preference: language})
    });
}

window.translatePage = translatePage;
window.persistLanguage = persistLanguage;
translatePage(localStorage.getItem('language_preference') || 'fr');