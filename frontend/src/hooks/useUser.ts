import { useEffect, useState } from 'react';
import api from '../api';

interface UserInfo {
    id: number;
    email: string;
    initials: string;
}

/**
 * Hook that fetches the currently logged-in user from /auth/me.
 * Returns { user, loading } where user is null while loading or if unauthenticated.
 */
export function useUser() {
    const [user, setUser] = useState<UserInfo | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (!token) {
            setLoading(false);
            return;
        }
        api.get('/auth/me')
            .then((res) => {
                const email: string = res.data.email;
                // Build initials: first letter of each part before @ split by dot
                const local = email.split('@')[0];
                const parts = local.split(/[._-]/);
                const initials = parts
                    .slice(0, 2)
                    .map((p) => p[0]?.toUpperCase() ?? '')
                    .join('');
                setUser({ id: res.data.id, email, initials: initials || email[0].toUpperCase() });
            })
            .catch(() => setUser(null))
            .finally(() => setLoading(false));
    }, []);

    return { user, loading };
}
