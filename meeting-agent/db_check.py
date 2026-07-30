import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:vasan5707@localhost:5432/meeting_agent_new')
    rows = await conn.fetch('SELECT id, title, status, meeting_date, start_time, LENGTH(COALESCE(transcript, \'\')) as tx_len FROM meetings')
    
    print("MEETINGS Table Status:")
    for row in rows:
        print(f"- {row['title']} | Date: {row['meeting_date']} | Status: {row['status']} | Transcript length: {row['tx_len']}")

if __name__ == "__main__":
    asyncio.run(main())
