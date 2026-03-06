import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import translations from '../i18n/translations';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLang] = useState('de');
  const [loaded, setLoaded] = useState(false);

  // Fetch language setting from backend
  useEffect(() => {
    const fetchLang = async () => {
      try {
        const res = await axios.get(`${API}/settings/language`);
        if (res.data?.language) setLang(res.data.language);
      } catch { /* default de */ }
      finally { setLoaded(true); }
    };
    fetchLang();
  }, []);

  // Translate function with interpolation
  const t = useCallback((key, params) => {
    let text = translations[lang]?.[key] || translations.de[key] || key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(`{${k}}`, v);
      });
    }
    return text;
  }, [lang]);

  const switchLang = useCallback((newLang) => {
    if (translations[newLang]) setLang(newLang);
  }, []);

  return (
    <I18nContext.Provider value={{ lang, t, switchLang, loaded }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}
