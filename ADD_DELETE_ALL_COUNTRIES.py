"""
QUICK FIX: Add Delete All Countries feature
This adds both frontend button and backend endpoint
"""

# ============= BACKEND CODE TO ADD =============
# Add this to backend/main.py after the existing countries endpoints (around line 810)

BACKEND_CODE = '''
@app.delete("/admin/countries/all")
async def delete_all_countries():
    """Delete ALL countries from database - FAST"""
    try:
        async with async_session() as session:
            from sqlalchemy import delete
            stmt = delete(Country)
            result = await session.execute(stmt)
            await session.commit()
            
            count = result.rowcount
            logger.info(f"✅ Deleted {count} countries")
            
            return {"success": True, "deleted": count}
    except Exception as e:
        logger.error(f"Error deleting all countries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
'''

# ============= FRONTEND CODE TO ADD =============
# In frontend/src/pages/Countries.jsx:
# 1. Add this function inside the Countries component (after fetchCountries):

FRONTEND_FUNCTION = '''
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
'''

#2. Add this button in the return section, after line 200 (before "All Countries" list):

FRONTEND_BUTTON = '''
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-white">All Countries ({countries.length})</h3>
                    <button
                        onClick={deleteAllCountries}
                        disabled={countries.length === 0}
                        className={`px-4 py-2 rounded-lg font-bold ${
                            countries.length === 0
                                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                : 'bg-red-600 hover:bg-red-700 text-white'
                        }`}
                    >
                        🗑️ Delete All
                    </button>
                </div>
'''

print("="*70)
print("DELETE ALL COUNTRIES - QUICK ADD")
print("="*70)
print("\n1. BACKEND (backend/main.py around line 810):")
print(BACKEND_CODE)
print("\n2. FRONTEND FUNCTION (Countries.jsx after fetchCountries):")
print(FRONTEND_FUNCTION)
print("\n3. FRONTEND BUTTON (Countries.jsx replace line 201):")
print(FRONTEND_BUTTON)
print("\n" + "="*70)
print("Copy these code blocks into the files manually!")
print("="*70)
