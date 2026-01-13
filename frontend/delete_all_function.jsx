const deleteAllCountries = async () => {
    if (!window.confirm('⚠️ DELETE ALL COUNTRIES? This cannot be undone!')) return;

    try {
        await axios.delete(`${API_BASE}/admin/countries/all`);
        alert('✅ All countries deleted!');
        await fetchCountries();
    } catch (error) {
        alert('❌ Error: ' + (error.response?.data?.detail || error.message));
    }
};
