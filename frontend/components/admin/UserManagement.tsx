"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { UserPlus, UserX, UserCheck, KeyRound } from "lucide-react";

interface UserRow {
  id: number;
  email: string;
  name: string;
  is_active: boolean;
  is_superuser: boolean;
  force_password_change: boolean;
  created_at: string;
}

export default function UserManagement() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [addError, setAddError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadUsers() {
    const { data } = await api.get("/api/admin/users");
    setUsers(data);
  }

  useEffect(() => { loadUsers(); }, []);

  async function handleAdd() {
    setAddError("");
    setLoading(true);
    try {
      await api.post("/api/admin/users", { email: newEmail, name: newName, password: newPwd });
      setShowAdd(false);
      setNewEmail(""); setNewName(""); setNewPwd("");
      await loadUsers();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setAddError(detail || "Failed to create user");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(user: UserRow) {
    if (user.is_active) {
      await api.post(`/api/admin/users/${user.id}/deactivate`).catch(() => {});
    } else {
      await api.post(`/api/admin/users/${user.id}/reactivate`).catch(() => {});
    }
    await loadUsers();
  }

  async function handleResetPwd(userId: number) {
    const pwd = prompt("Enter new temporary password (min 8 chars):");
    if (!pwd || pwd.length < 8) return;
    await api.post(`/api/admin/users/${userId}/reset-password`, { new_password: pwd }).catch(() => {});
    alert("Password reset. User will be prompted to change on next login.");
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">User Management</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <UserPlus size={15} />
          Add User
        </button>
      </div>

      {/* Add user modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Add New User</h2>
            <div className="space-y-3">
              <input placeholder="Full name" value={newName} onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input placeholder="Email" type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input placeholder="Temporary password" type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              {addError && <p className="text-red-600 text-sm">{addError}</p>}
              <p className="text-xs text-slate-500">User will be asked to change their password on first login.</p>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={handleAdd} disabled={loading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white text-sm font-medium py-2 rounded-lg transition-colors">
                {loading ? "Creating…" : "Create User"}
              </button>
              <button onClick={() => setShowAdd(false)}
                className="flex-1 border border-slate-200 text-slate-700 text-sm font-medium py-2 rounded-lg hover:bg-slate-50 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="text-left px-4 py-3 text-slate-600 font-medium">Name</th>
              <th className="text-left px-4 py-3 text-slate-600 font-medium">Email</th>
              <th className="text-left px-4 py-3 text-slate-600 font-medium">Status</th>
              <th className="text-left px-4 py-3 text-slate-600 font-medium">Role</th>
              <th className="text-right px-4 py-3 text-slate-600 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-3 font-medium text-slate-800">{u.name}</td>
                <td className="px-4 py-3 text-slate-600">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${u.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? "bg-green-500" : "bg-slate-400"}`} />
                    {u.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.is_superuser ? (
                    <span className="text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">Superuser</span>
                  ) : (
                    <span className="text-xs text-slate-500">User</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {!u.is_superuser && (
                      <button onClick={() => handleToggle(u)} title={u.is_active ? "Deactivate" : "Reactivate"}
                        className="p-1.5 rounded text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors">
                        {u.is_active ? <UserX size={15} /> : <UserCheck size={15} />}
                      </button>
                    )}
                    <button onClick={() => handleResetPwd(u.id)} title="Reset password"
                      className="p-1.5 rounded text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors">
                      <KeyRound size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
