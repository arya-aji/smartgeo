"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getOperators, createOperator, updateOperator } from "@/lib/api";
import type { OperatorResponse, Role } from "@/lib/types";
import DataTable from "@/components/DataTable";
import { showToast } from "@/components/Toast";
import { isAdmin } from "@/lib/auth";

export default function OperatorsPage() {
  const router = useRouter();
  const [operators, setOperators] = useState<OperatorResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "",
    username: "",
    password: "",
    role: "OPERATOR" as Role,
    is_active: true,
  });

  useEffect(() => {
    if (!isAdmin()) {
      router.push("/maps");
      return;
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await getOperators();
      setOperators(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load operators";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setForm({ name: "", username: "", password: "", role: "OPERATOR", is_active: true });
    setEditingId(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        const payload: { name?: string; password?: string; is_active?: boolean; role?: Role } = {};
        if (form.name) payload.name = form.name;
        if (form.password) payload.password = form.password;
        payload.is_active = form.is_active;
        payload.role = form.role;
        await updateOperator(editingId, payload);
        showToast("Operator updated", "success");
      } else {
        await createOperator({
          name: form.name,
          username: form.username,
          password: form.password,
          role: form.role,
        });
        showToast("Operator created", "success");
      }
      resetForm();
      setShowForm(false);
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      showToast(msg, "error");
    }
  };

  const startEdit = (op: OperatorResponse) => {
    setForm({
      name: op.name,
      username: op.username,
      password: "",
      role: op.role,
      is_active: op.is_active,
    });
    setEditingId(op.id);
    setShowForm(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-surface-900">Operators</h1>
        <button
          onClick={() => {
            resetForm();
            setShowForm((s) => !s);
          }}
          className="rounded-md bg-surface-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-surface-800"
        >
          {showForm ? "Cancel" : "Add Operator"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-surface-700">Name</label>
              <input
                required={!editingId}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="mt-1 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700">Username</label>
              <input
                required={!editingId}
                disabled={!!editingId}
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                className="mt-1 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500 disabled:bg-surface-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700">
                Password {editingId && "(leave blank to keep)"}
              </label>
              <input
                type="password"
                required={!editingId}
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                className="mt-1 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700">Role</label>
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as Role }))}
                className="mt-1 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
              >
                <option value="OPERATOR">Operator</option>
                <option value="ADMIN">Admin</option>
              </select>
            </div>
            <div className="flex items-center gap-2 sm:col-span-2">
              <input
                type="checkbox"
                id="is_active"
                checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="rounded border-surface-300 text-surface-900 focus:ring-surface-500"
              />
              <label htmlFor="is_active" className="text-sm text-surface-700">
                Active
              </label>
            </div>
          </div>
          <div className="mt-4">
            <button
              type="submit"
              className="rounded-md bg-surface-900 px-4 py-2 text-sm font-medium text-white hover:bg-surface-800"
            >
              {editingId ? "Update" : "Create"}
            </button>
          </div>
        </form>
      )}

      <DataTable
        columns={[
          { key: "name", header: "Name" },
          { key: "username", header: "Username" },
          { key: "role", header: "Role" },
          {
            key: "active",
            header: "Active",
            render: (row) => (row.is_active ? "Yes" : "No"),
          },
          { key: "completed", header: "Completed", className: "text-right" },
          { key: "assigned", header: "Assigned", className: "text-right" },
          {
            key: "actions",
            header: "",
            render: (row) => (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  startEdit(row);
                }}
                className="text-sm font-medium text-surface-600 hover:text-surface-900"
              >
                Edit
              </button>
            ),
          },
        ]}
        rows={operators}
        keyExtractor={(r) => r.id}
        loading={loading}
        emptyText="No operators found"
      />
    </div>
  );
}
