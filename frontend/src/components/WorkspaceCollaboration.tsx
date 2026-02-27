import React, { useState, useEffect } from 'react';
import { Users, UserPlus, Mail, Trash2, Crown, Eye, Edit, Loader2 } from 'lucide-react';
import api from '../api';
import { useToast } from '../contexts/ToastContext';

interface Collaborator {
  id: number;
  email: string;
  name?: string;
  role: 'owner' | 'viewer' | 'editor' | 'admin';
  joined_at: string;
  avatar?: string;
}

interface WorkspaceCollaborationProps {
  workspaceId: number;
  workspaceName: string;
  currentUserRole: 'owner' | 'admin' | 'editor' | 'viewer';
  onCollaborationChange?: () => void;
}

type PermissionLevel = 'viewer' | 'editor' | 'admin';

const WorkspaceCollaboration: React.FC<WorkspaceCollaborationProps> = ({
  workspaceId,
  workspaceName,
  currentUserRole,
  onCollaborationChange
}) => {
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<PermissionLevel>('viewer');
  const [inviting, setInviting] = useState(false);
  const [updatingRole, setUpdatingRole] = useState<number | null>(null);
  const [removingUser, setRemovingUser] = useState<number | null>(null);
  const { success: showSuccess, error: showError } = useToast();

  // Check if current user can manage collaborators
  const canManageCollaborators = ['owner', 'admin'].includes(currentUserRole);

  useEffect(() => {
    loadCollaborators();
  }, [workspaceId]);

  const loadCollaborators = async () => {
    try {
      const response = await api.get(`/workspaces/${workspaceId}/collaborators`);
      setCollaborators(response.data);
    } catch (error) {
      showError('Failed to load collaborators');
    } finally {
      setLoading(false);
    }
  };

  const handleInviteUser = async () => {
    if (!inviteEmail.trim()) {
      showError('Please enter an email address');
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(inviteEmail)) {
      showError('Please enter a valid email address');
      return;
    }

    setInviting(true);
    try {
      await api.post(`/workspaces/${workspaceId}/collaborators`, {
        email: inviteEmail.trim(),
        role: inviteRole
      });

      showSuccess(`Invitation sent to ${inviteEmail}`);
      setInviteEmail('');
      setInviteRole('viewer');
      setShowInviteModal(false);
      loadCollaborators();
      onCollaborationChange?.();
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to send invitation';
      showError(message);
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateRole = async (userId: number, newRole: PermissionLevel) => {
    setUpdatingRole(userId);
    try {
      await api.patch(`/workspaces/${workspaceId}/collaborators/${userId}`, {
        role: newRole
      });

      showSuccess('User role updated successfully');
      loadCollaborators();
      onCollaborationChange?.();
    } catch (error) {
      showError('Failed to update user role');
    } finally {
      setUpdatingRole(null);
    }
  };

  const handleRemoveUser = async (userId: number, userEmail: string) => {
    if (!confirm(`Are you sure you want to remove ${userEmail} from this workspace?`)) {
      return;
    }

    setRemovingUser(userId);
    try {
      await api.delete(`/workspaces/${workspaceId}/collaborators/${userId}`);
      showSuccess('User removed from workspace');
      loadCollaborators();
      onCollaborationChange?.();
    } catch (error) {
      showError('Failed to remove user');
    } finally {
      setRemovingUser(null);
    }
  };

  const getRoleIcon = (role: Collaborator['role']) => {
    switch (role) {
      case 'owner':
        return <Crown className="h-4 w-4 text-amber-600" />;
      case 'admin':
        return <Crown className="h-4 w-4 text-purple-600" />;
      case 'editor':
        return <Edit className="h-4 w-4 text-blue-600" />;
      case 'viewer':
        return <Eye className="h-4 w-4 text-green-600" />;
      default:
        return <Eye className="h-4 w-4 text-gray-600" />;
    }
  };

  const getRoleLabel = (role: Collaborator['role']) => {
    switch (role) {
      case 'owner':
        return 'Owner';
      case 'admin':
        return 'Admin';
      case 'editor':
        return 'Editor';
      case 'viewer':
        return 'Viewer';
      default:
        return 'Viewer';
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          <span className="text-slate-600 dark:text-slate-400">Loading collaborators...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Users className="h-5 w-5 text-slate-600 dark:text-slate-400" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Workspace Collaboration
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {collaborators.length} collaborator{collaborators.length !== 1 ? 's' : ''} in {workspaceName}
            </p>
          </div>
        </div>

        {canManageCollaborators && (
          <button
            onClick={() => setShowInviteModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <UserPlus className="h-4 w-4" />
            Invite User
          </button>
        )}
      </div>

      {/* Current Collaborators */}
      <div className="space-y-4">
        {collaborators.map((collaborator) => (
          <div key={collaborator.id} className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-medium">
                {collaborator.avatar ? (
                  <img src={collaborator.avatar} alt={collaborator.name || collaborator.email} className="w-10 h-10 rounded-full object-cover" />
                ) : (
                  (collaborator.name || collaborator.email).charAt(0).toUpperCase()
                )}
              </div>
              <div>
                <p className="font-medium text-slate-900 dark:text-slate-100">
                  {collaborator.name || collaborator.email}
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {collaborator.email}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {canManageCollaborators && collaborator.role !== 'owner' ? (
                <select
                  value={collaborator.role}
                  onChange={(e) => handleUpdateRole(collaborator.id, e.target.value as PermissionLevel)}
                  disabled={updatingRole === collaborator.id}
                  className="px-3 py-1 text-sm border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-50"
                >
                  <option value="viewer">Viewer</option>
                  <option value="editor">Editor</option>
                  <option value="admin">Admin</option>
                </select>
              ) : (
                <div className="flex items-center gap-2 px-3 py-1 bg-slate-100 dark:bg-slate-600 rounded-md">
                  {getRoleIcon(collaborator.role)}
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {getRoleLabel(collaborator.role)}
                  </span>
                </div>
              )}

              {updatingRole === collaborator.id && (
                <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
              )}

              {canManageCollaborators && collaborator.role !== 'owner' && (
                <button
                  onClick={() => handleRemoveUser(collaborator.id, collaborator.email)}
                  disabled={removingUser === collaborator.id}
                  className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors disabled:opacity-50"
                  title="Remove from workspace"
                >
                  {removingUser === collaborator.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Role Permissions Info */}
      <div className="mt-6 p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
        <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
          Permission Levels
        </h4>
        <div className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
          <div className="flex items-center gap-2">
            <Crown className="h-3 w-3 text-purple-600" />
            <strong>Admin:</strong> Can manage workspace and collaborators
          </div>
          <div className="flex items-center gap-2">
            <Edit className="h-3 w-3 text-blue-600" />
            <strong>Editor:</strong> Can add/edit papers and settings
          </div>
          <div className="flex items-center gap-2">
            <Eye className="h-3 w-3 text-green-600" />
            <strong>Viewer:</strong> Can view papers and export data
          </div>
        </div>
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Invite Collaborator
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Permission Level
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as PermissionLevel)}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="viewer">Viewer - Can view papers and export data</option>
                  <option value="editor">Editor - Can add/edit papers and settings</option>
                  <option value="admin">Admin - Can manage workspace and collaborators</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowInviteModal(false)}
                className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-md hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleInviteUser}
                disabled={inviting || !inviteEmail.trim()}
                className="flex-1 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-md transition-colors flex items-center justify-center gap-2"
              >
                {inviting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Mail className="h-4 w-4" />
                    Send Invite
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkspaceCollaboration;
