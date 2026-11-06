import { useCallback, useEffect, useMemo, useState } from 'react';
import api from '../services/api';
import { AuthContext } from './authContextValue';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(sessionStorage.getItem('access_token')));

  useEffect(() => {
    if (!sessionStorage.getItem('access_token')) {
      return;
    }

    api.get('/auth/eu')
      .then(({ data }) => setUser(data))
      .catch(() => {
        sessionStorage.removeItem('access_token');
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (login, senha) => {
    const form = new URLSearchParams({ username: login, password: senha });
    const { data } = await api.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    sessionStorage.setItem('access_token', data.access_token);
    try {
      const { data: identity } = await api.get('/auth/eu');
      setUser(identity);
    } catch (error) {
      sessionStorage.removeItem('access_token');
      throw error;
    }
  }, []);

  const register = useCallback(async ({ login, nome, senha }) => {
    const { data } = await api.post('/auth/registrar', { login, nome, senha });
    sessionStorage.setItem('access_token', data.access_token);
    try {
      const { data: identity } = await api.get('/auth/eu');
      setUser(identity);
    } catch (error) {
      sessionStorage.removeItem('access_token');
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem('access_token');
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
