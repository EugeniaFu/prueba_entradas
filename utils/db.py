import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host='database-1.cf0ey64ia6yt.us-east-2.rds.amazonaws.com',
        user='admin',
        password='12345678',
        database='andamiosdb'
    )
    return connection