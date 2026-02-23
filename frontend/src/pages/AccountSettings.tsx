import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  Check,
  KeyRound,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../api';
import { asApiError, apiErrorMessage } from '../utils/apiError';

interface UserProfile {
  id: number;
  email: string;
  google_id?: string;
  google_email?: string;
  name?: string;
  profile_pic?: string;
}

const AccountSettings: React.FC = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  const [confirmEmail, setConfirmEmail] = useState('');

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await api.get('/auth/me');
      setProfile(res.data);
      setName(res.data.name || '');
      setEmail(res.data.email);
    } catch (err: unknown) {
      const apiErr = asApiError(err);
      if (apiErr.response?.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
        return;
      }
      setError('Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!profile) {
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await api.patch('/auth/me', { name });
      setSuccess('Profile updated successfully');
      setEditMode(false);
      await fetchProfile();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to update profile'));
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('Please fill all password fields');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to change password'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!profile) {
      return;
    }
    if (!confirmEmail.trim()) {
      setError('Please type your account email to confirm deletion');
      return;
    }
    if (!profile.google_id && !deletePassword) {
      setError('Current password is required to delete account');
      return;
    }

    setDeleting(true);
    setError(null);
    setSuccess(null);
    try {
      await api.delete('/auth/me', {
        data: {
          confirm_email: confirmEmail,
          password: profile.google_id ? undefined : deletePassword,
        },
      });
      localStorage.removeItem('token');
      navigate('/login');
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to delete account'));
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
        </div>
      </Layout>
    );
  }

  if (!profile) {
    return (
      <Layout>
        <div className="studio-panel-quiet p-10 text-center">
          <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-2" />
          <p className="text-sm text-slate-600">Failed to load profile.</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="page-enter max-w-4xl">
        <section className="studio-hero mb-5">
          <span className="studio-kicker">
            <Sparkles className="h-3.5 w-3.5" />
            Identity center
          </span>
          <h2>Account Settings</h2>
          <p>
            Manage profile details, security credentials, and account lifecycle actions from one place.
          </p>
          <div className="studio-chip-row">
            <span className="studio-chip">{profile.google_id ? 'Google linked' : 'Password account'}</span>
            <span className="studio-chip">{profile.email}</span>
          </div>
          <div className="studio-orb" aria-hidden="true" />
        </section>

        <section className="studio-surface p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h3 className="text-base font-semibold text-slate-900 inline-flex items-center gap-2">
              <UserRound className="h-4.5 w-4.5 text-indigo-600" />
              Profile Information
            </h3>
            <button onClick={() => setEditMode((prev) => !prev)} className="hero-btn-secondary">
              {editMode ? 'Cancel edit' : 'Edit profile'}
            </button>
          </div>

          <div className="flex items-center gap-4 mb-4">
            <div className="h-16 w-16 rounded-full bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center text-white text-xl font-bold">
              {profile.profile_pic ? (
                <img src={profile.profile_pic} alt="Profile" className="h-16 w-16 rounded-full object-cover" />
              ) : (
                (profile.name || profile.email).charAt(0).toUpperCase()
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">{profile.name || 'No name set'}</p>
              <p className="text-sm text-slate-500">{profile.email}</p>
              {profile.google_id && (
                <p className="text-xs text-emerald-600 mt-1 inline-flex items-center gap-1">
                  <Check className="h-3.5 w-3.5" />
                  Connected with Google
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="studio-panel-quiet p-3">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!editMode}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 disabled:text-slate-500"
                placeholder="Your name"
              />
            </div>
            <div className="studio-panel-quiet p-3">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                disabled
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-500 bg-slate-100"
              />
              <p className="text-xs text-slate-500 mt-1">Email address cannot be changed here.</p>
            </div>
          </div>

          {editMode && (
            <div className="mt-3">
              <button onClick={handleSaveProfile} disabled={saving} className="hero-btn-primary">
                {saving ? 'Saving...' : 'Save profile changes'}
              </button>
            </div>
          )}
        </section>

        <section className="studio-surface p-4 mb-4">
          <h3 className="text-base font-semibold text-slate-900 inline-flex items-center gap-2 mb-3">
            <ShieldCheck className="h-4.5 w-4.5 text-cyan-600" />
            Security
          </h3>
          {!profile.google_id ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="studio-panel-quiet p-3">
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                  Current password
                </label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Enter current password"
                />
              </div>
              <div className="studio-panel-quiet p-3">
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                  New password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Enter new password"
                />
              </div>
              <div className="studio-panel-quiet p-3 md:col-span-2">
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                  Confirm new password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Confirm new password"
                />
              </div>
              <div className="md:col-span-2">
                <button onClick={handleChangePassword} disabled={saving} className="hero-btn-primary">
                  <KeyRound className="h-4 w-4" />
                  {saving ? 'Changing password...' : 'Change password'}
                </button>
              </div>
            </div>
          ) : (
            <div className="studio-panel-quiet p-3">
              <p className="text-sm text-emerald-700">
                This account uses Google authentication. Password changes are managed by your Google
                account.
              </p>
            </div>
          )}
        </section>

        <section className="studio-surface p-4">
          <h3 className="text-base font-semibold text-red-700 inline-flex items-center gap-2 mb-3">
            <Trash2 className="h-4.5 w-4.5" />
            Danger Zone
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="studio-panel-quiet p-3">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                Confirm account email
              </label>
              <input
                type="email"
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-red-400"
                placeholder={profile.email}
              />
            </div>
            {!profile.google_id && (
              <div className="studio-panel-quiet p-3">
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                  Current password
                </label>
                <input
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-red-400"
                  placeholder="Enter current password"
                />
              </div>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Deleting the account removes workspaces, papers, and chat history permanently.
          </p>
          <button
            onClick={handleDeleteAccount}
            disabled={deleting}
            className="mt-3 rounded-xl border border-red-300 px-3.5 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-60"
          >
            {deleting ? 'Deleting account...' : 'Delete account'}
          </button>
        </section>

        {error && (
          <div className="toast-floating text-sm text-red-700 border-red-200 bg-red-50 flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
            <button onClick={() => setError(null)}>
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {success && (
          <div className="toast-floating text-sm text-emerald-700 border-emerald-200 bg-emerald-50 flex items-center gap-2">
            <Check className="h-4 w-4" />
            <span>{success}</span>
            <button onClick={() => setSuccess(null)}>
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AccountSettings;
