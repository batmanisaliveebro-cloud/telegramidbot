import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const PaymentSettings = () => {
    const [upiId, setUpiId] = useState('');
    const [qrImage, setQrImage] = useState(null); // File object
    const [qrPreview, setQrPreview] = useState(''); // URL for preview
    const [channelLink, setChannelLink] = useState('');
    const [ownerUsername, setOwnerUsername] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [webhookFixing, setWebhookFixing] = useState(false);
    const [webhookMessage, setWebhookMessage] = useState('');
    const navigate = useNavigate();

    const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

    useEffect(() => {
        fetchSettings();
    }, []);

    const fetchSettings = async () => {
        try {
            const token = localStorage.getItem('admin_token');
            if (!token) {
                navigate('/login');
                return;
            }
            // Add auth header if needed, currently API might be open or basic
            // Assuming simple access for now based on main.py
            const response = await axios.get(`${API_BASE}/admin/settings/payment`);
            setUpiId(response.data.upi_id || '');
            setQrPreview(response.data.qr_image || '');
            setChannelLink(response.data.channel_link || '');
            setOwnerUsername(response.data.owner_username || '');
            setLoading(false);
        } catch (error) {
            console.error("Error fetching settings:", error);
            setMessage("Failed to load settings.");
            setLoading(false);
        }
    };

    const handleImageChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            setQrImage(file);
            // Create local preview
            const reader = new FileReader();
            reader.onloadend = () => {
                setQrPreview(reader.result);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setMessage('');

        const formData = new FormData();
        formData.append('upi_id', upiId);
        formData.append('channel_link', channelLink);
        formData.append('owner_username', ownerUsername);
        if (qrImage) {
            formData.append('qr_image', qrImage);
        }

        try {
            await axios.post(`${API_BASE}/admin/settings/payment`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            setMessage('✅ Settings updated successfully!');
            fetchSettings(); // Refresh to get server URLs
        } catch (error) {
            console.error("Error saving settings:", error);
            setMessage('❌ Failed to save settings.');
        } finally {
            setSaving(false);
        }
    };

    const handleFixWebhook = async () => {
        setWebhookFixing(true);
        setWebhookMessage('');

        try {
            const response = await axios.post(`${API_BASE}/api/fix-webhook`);

            if (response.data.success) {
                setWebhookMessage(`✅ ${response.data.message}`);
                if (response.data.webhook_info) {
                    console.log('Webhook Info:', response.data.webhook_info);
                }
            } else {
                setWebhookMessage(`❌ ${response.data.message}`);
            }
        } catch (error) {
            console.error("Error fixing webhook:", error);
            setWebhookMessage('❌ Failed to fix webhook. Check backend logs.');
        } finally {
            setWebhookFixing(false);
        }
    };

    if (loading) return <div className="p-8 text-white">Loading settings...</div>;

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold text-white mb-8">💳 Payment Settings</h1>

            <div className="bg-slate-800 rounded-xl p-8 border border-slate-700 shadow-lg">
                <form onSubmit={handleSubmit} className="space-y-8">

                    {/* UPI ID Section */}
                    <div>
                        <label className="block text-slate-400 text-sm font-medium mb-2">
                            UPI ID (VPA)
                        </label>
                        <input
                            type="text"
                            value={upiId}
                            onChange={(e) => setUpiId(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-purple-500 outline-none transition-all"
                            placeholder="e.g. business@upi"
                            required
                        />
                        <p className="text-xs text-slate-500 mt-2">
                            This UPI ID will be shown to users for manual deposits.
                        </p>
                    </div>

                    {/* QR Code Section */}
                    <div>
                        <label className="block text-slate-400 text-sm font-medium mb-4">
                            QR Code Image
                        </label>

                        <div className="flex flex-col md:flex-row gap-8 items-start">

                            {/* Preview Area */}
                            <div className="w-48 h-48 bg-slate-900 rounded-lg border-2 border-dashed border-slate-700 flex items-center justify-center overflow-hidden relative">
                                {qrPreview ? (
                                    <img
                                        src={qrPreview}
                                        alt="QR Code"
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <span className="text-slate-600 text-sm">No QR Uploaded</span>
                                )}
                            </div>

                            {/* Upload Controls */}
                            <div className="flex-1">
                                <label className="cursor-pointer bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-medium transition-colors inline-block mb-3">
                                    <span>Upload New QR Code</span>
                                    <input
                                        type="file"
                                        accept="image/*"
                                        onChange={handleImageChange}
                                        className="hidden"
                                    />
                                </label>
                                <p className="text-sm text-slate-400">
                                    Supports JPG, PNG, WEBP. <br />
                                    Max file size: 5MB.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Bot Configuration Section */}
                    <div className="border-t border-slate-700 pt-8 mt-8">
                        <h3 className="text-xl font-bold text-white mb-6">📢 Bot Configuration</h3>

                        <div className="space-y-6">
                            {/* Channel Link */}
                            <div>
                                <label className="block text-slate-400 text-sm font-medium mb-2">
                                    Channel Link
                                </label>
                                <input
                                    type="url"
                                    value={channelLink}
                                    onChange={(e) => setChannelLink(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-purple-500 outline-none transition-all"
                                    placeholder="https://t.me/yourchannel"
                                />
                                <p className="text-xs text-slate-500 mt-2">
                                    Telegram channel link for updates and announcements
                                </p>
                            </div>

                            {/* Owner Username */}
                            <div>
                                <label className="block text-slate-400 text-sm font-medium mb-2">
                                    Owner Username
                                </label>
                                <input
                                    type="text"
                                    value={ownerUsername}
                                    onChange={(e) => setOwnerUsername(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-purple-500 outline-none transition-all"
                                    placeholder="@yourusername"
                                />
                                <p className="text-xs text-slate-500 mt-2">
                                    Admin username for user support
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Submit Button */}
                    <div className="pt-4 border-t border-slate-700">
                        <button
                            type="submit"
                            disabled={saving}
                            className={`w-full py-3 rounded-lg font-bold text-lg transition-all ${saving
                                ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                                : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white shadow-lg shadow-purple-900/50'
                                }`}
                        >
                            {saving ? 'Saving...' : '💾 Save Payment Settings'}
                        </button>
                    </div>

                    {/* Feedback Message */}
                    {message && (
                        <div className={`p-4 rounded-lg text-center font-medium ${message.includes('✅')
                            ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                            }`}>
                            {message}
                        </div>
                    )}

                </form>
            </div>

            {/* Webhook Fix Section */}
            <div className="mt-8 bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h3 className="text-xl font-bold text-white mb-4">🔗 Webhook Management</h3>
                <p className="text-slate-400 text-sm mb-6">
                    Use this button after every deployment to refresh the webhook connection.
                    This ensures the bot always responds to messages.
                </p>

                <button
                    onClick={handleFixWebhook}
                    disabled={webhookFixing}
                    className={`w-full py-3 rounded-lg font-bold text-lg transition-all ${webhookFixing
                            ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                            : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white shadow-lg shadow-blue-900/50'
                        }`}
                >
                    {webhookFixing ? '🔄 Fixing Webhook...' : '🔧 Fix Webhook Now'}
                </button>

                {webhookMessage && (
                    <div className={`mt-4 p-4 rounded-lg text-center font-medium ${webhookMessage.includes('✅')
                            ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                        {webhookMessage}
                    </div>
                )}
            </div>

            <div className="mt-8 bg-blue-500/10 border border-blue-500/20 p-6 rounded-xl">
                <h3 className="text-blue-400 font-bold mb-2">ℹ️ How this works</h3>
                <p className="text-slate-300 text-sm">
                    Changes made here are <b>updated instantly</b> on the Telegram Bot.
                    When a user clicks "Determine Payment", the bot fetches the latest UPI ID and QR Code from here directly.
                    No need to restart the bot!
                </p>
            </div>
        </div>
    );
};

export default PaymentSettings;
