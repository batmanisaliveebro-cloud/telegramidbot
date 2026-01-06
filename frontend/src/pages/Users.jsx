import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { User, ChevronRight, Search, DollarSign, X } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://welldecked-deflected-daniella.ngrok-free.dev';

const Users = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [showModal, setShowModal] = useState(false);
    const [selectedUser, setSelectedUser] = useState(null);
    const [adjustType, setAdjustType] = useState('admin_add');
    const [amount, setAmount] = useState('');
    const [toast, setToast] = useState(null);

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        try {
            const res = await axios.get(`${API_BASE}/admin/users`);
            setUsers(res.data);
        } catch (err) {
            console.error("Error fetching users:", err);
        } finally {
            setLoading(false);
        }
    };

    const showToast = (message, type = 'success') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    const handleAdjustBalance = async () => {
        if (!amount || isNaN(amount) || parseFloat(amount) <= 0) {
            showToast('Please enter a valid amount', 'error');
            return;
        }

        try {
            const adjustmentAmount = adjustType === 'admin_add'
                ? parseFloat(amount)
                : -parseFloat(amount);

            await axios.post(`${API_BASE}/admin/users/${selectedUser.id}/adjust-balance`, {
                amount: adjustmentAmount,
                reason: adjustType
            });

            showToast(`Balance ${adjustType === 'admin_add' ? 'added' : 'deducted'} successfully!`);
            setShowModal(false);
            setAmount('');
            fetchUsers(); // Refresh list
        } catch (err) {
            console.error('Error adjusting balance:', err);
            showToast('Failed to adjust balance', 'error');
        }
    };

    const openModal = (user, e) => {
        e.preventDefault();
        e.stopPropagation();
        setSelectedUser(user);
        setShowModal(true);
    };

    const filteredUsers = users.filter(u =>
        (u.username && u.username.toLowerCase().includes(search.toLowerCase())) ||
        (u.telegram_id.toString().includes(search)) ||
        (u.full_name && u.full_name.toLowerCase().includes(search.toLowerCase()))
    );

    if (loading) return <div className="text-center text-gray-400 py-10">Loading users...</div>;

    return (
        <div className="space-y-6 animate-in">
            {/* Toast Notification */}
            {toast && (
                <div className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-lg shadow-lg ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
                    } text-white font-medium animate-in`}>
                    {toast.message}
                </div>
            )}

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-2xl font-bold">User Management</h2>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
                    <input
                        type="text"
                        placeholder="Search users..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="bg-gray-800 border-none rounded-xl pl-10 pr-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 w-full md:w-64"
                    />
                </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
                {filteredUsers.map(user => (
                    <div
                        key={user.id}
                        className="bg-gray-800/50 p-4 rounded-2xl border border-gray-700 hover:border-blue-500 transition-all flex items-center justify-between group"
                    >
                        <Link to={`/users/${user.id}`} className="flex items-center space-x-4 flex-1">
                            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                                <User className="text-white" size={24} />
                            </div>
                            <div>
                                <h3 className="font-semibold">{user.full_name}</h3>
                                <p className="text-sm text-gray-400">@{user.username || 'N/A'} • {user.telegram_id}</p>
                            </div>
                        </Link>
                        <div className="text-right flex items-center space-x-4">
                            <div>
                                <p className="text-xs text-gray-500 uppercase tracking-wider">Balance</p>
                                <p className="text-lg font-bold text-green-400">₹{user.balance.toFixed(2)}</p>
                            </div>
                            <button
                                onClick={(e) => openModal(user, e)}
                                className="p-2 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                                title="Adjust Balance"
                            >
                                <DollarSign size={20} />
                            </button>
                            <Link to={`/users/${user.id}`}>
                                <ChevronRight className="text-gray-600 group-hover:text-blue-400 transition-colors" />
                            </Link>
                        </div>
                    </div>
                ))}

                {filteredUsers.length === 0 && (
                    <div className="text-center py-20 text-gray-500">
                        No users found matching "{search}"
                    </div>
                )}
            </div>

            {/* Balance Adjustment Modal */}
            {showModal && selectedUser && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-800 rounded-2xl p-6 max-w-md w-full border border-gray-700">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-xl font-bold">Adjust Balance</h3>
                            <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-white">
                                <X size={24} />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div className="bg-gray-700/50 p-4 rounded-lg">
                                <p className="text-sm text-gray-400">User</p>
                                <p className="font-semibold">{selectedUser.full_name}</p>
                                <p className="text-sm text-gray-400">Current Balance: ₹{selectedUser.balance.toFixed(2)}</p>
                            </div>

                            <div>
                                <label className="block text-sm mb-2 text-gray-400">Action</label>
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        onClick={() => setAdjustType('admin_add')}
                                        className={`py-2 px-4 rounded-lg font-medium transition-all ${adjustType === 'admin_add'
                                                ? 'bg-green-500 text-white'
                                                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                            }`}
                                    >
                                        Add Points
                                    </button>
                                    <button
                                        onClick={() => setAdjustType('admin_deduct')}
                                        className={`py-2 px-4 rounded-lg font-medium transition-all ${adjustType === 'admin_deduct'
                                                ? 'bg-red-500 text-white'
                                                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                            }`}
                                    >
                                        Deduct Points
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm mb-2 text-gray-400">Amount (₹)</label>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={amount}
                                    onChange={(e) => setAmount(e.target.value)}
                                    className="w-full bg-gray-700 border-none rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500"
                                    placeholder="Enter amount"
                                />
                            </div>

                            <div className="flex gap-2 pt-4">
                                <button
                                    onClick={() => setShowModal(false)}
                                    className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 px-4 rounded-lg font-medium transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleAdjustBalance}
                                    className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded-lg font-medium transition-colors"
                                >
                                    Confirm
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Users;
