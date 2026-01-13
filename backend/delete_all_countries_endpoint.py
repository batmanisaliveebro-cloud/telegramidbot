@app.delete("/admin/countries/all")
async def delete_all_countries():
    """Delete ALL countries from database"""
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
