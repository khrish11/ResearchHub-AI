import { useEffect, useState } from 'react';
import api from '../api';

interface UserInfo {
    id: number;
    email: string;
    initials: string;
    isDeveloper: boolean;
    canAccessAnalytics: boolean;
}

/**
 * Hook that fetches the currently logged-in user from /auth/me.
 * Returns { user, loading } where user is null while loading or if unauthenticated.
 */
export function useUser() {
    const [user, setUser] = useState<UserInfo | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = () => {
            setLoading(true);
            api.get('/auth/me')
                .then((res) => {
                    const email: string = res.data.email;
                    const isDeveloper = Boolean(res.data.is_developer);
                    const canAccessAnalytics = Boolean(res.data.can_access_analytics);
                    // Build initials: first letter of each part before @ split by dot
                    const local = email.split('@')[0];
                    const parts = local.split(/[._-]/);
                    const initials = parts
                        .slice(0, 2)
                        .map((p) => p[0]?.toUpperCase() ?? '')
                        .join('');
                    setUser({
                        id: res.data.id,
                        email,
                        initials: initials || email[0].toUpperCase(),
                        isDeveloper,
                        canAccessAnalytics,
                    });
                })
                .catch(() => setUser(null))
                .finally(() => setLoading(false));
        };

        load();
        const onSessionChange = () => load();
        window.addEventListener('auth-session-changed', onSessionChange);
        return () => window.removeEventListener('auth-session-changed', onSessionChange);
    }, []);

    return { user, loading };
}
