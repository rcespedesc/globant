from unicodedata import name
from unittest import result
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd
import logging
from fastavro import writer, reader, parse_schema, schemaless_writer

CHUNK_SIZE = 1000

############################
### Function to read a csv in chunks and upload it to snowflake without null records
###########################


def load_csv(
    credentials, destination, filename, colnames, datatypes
):

    conn = snowflake.connector.connect(
        user=credentials["user"],
        password=credentials["password"],
        account=credentials["account"],
    )

    cs = conn.cursor()
    try:
        cs.execute(f"USE DATABASE GLOBANT")
        cs.execute(f"USE SCHEMA PUBLIC")
        df = pd.DataFrame()
        for chunk in pd.read_csv(
            filename,
            chunksize=CHUNK_SIZE,
            names=colnames,
            on_bad_lines="skip",
            dtype=datatypes,
        ):
            df = pd.concat([df,chunk[chunk.isnull().any(axis=1)]])
            chunk.dropna(axis=0, inplace=True)
            write_pandas(conn, chunk, destination)
        logging.info(f"File {filename} was uploaded")

        return df

    except Exception as e:
        print(e)

        return 0
    finally:
        cs.close()

############################
### Function to read a table from snowflake and create an avro file for backup
###########################
def backup_table(credentials, tablename, schema):
    conn = snowflake.connector.connect(
        user=credentials["user"],
        password=credentials["password"],
        account=credentials["account"],
    )

    cs = conn.cursor()

    try:
        query = f"SELECT * FROM {tablename}"
        cs.execute(f"USE DATABASE GLOBANT")
        cs.execute(f"USE SCHEMA PUBLIC")
        cs.execute(query)
        results = cs.fetchall()
        rows = []

        # Parse to dict
        for row in results:
            new_row = {}
            for i in range(len(schema["fields"])):
                new_row[schema["fields"][i]["name"]] = row[i]
            rows.append(new_row)

        parsed_schema = parse_schema(schema)

        with open(f"avro_backup/{tablename}.avro", "wb") as out:
            writer(out, parsed_schema, rows)

        return 1
    except Exception as e:
        print(e)

        return 0
    finally:
        cs.close()

############################
### Function to read an avro file and upload the data to snowflake
###########################
def restore_table(credentials, tablename):

    conn = snowflake.connector.connect(
        user=credentials["user"],
        password=credentials["password"],
        account=credentials["account"],
    )

    cs = conn.cursor()

    try:
        cs.execute(f"USE DATABASE GLOBANT")
        cs.execute(f"USE SCHEMA PUBLIC")
        cs.execute(f"TRUNCATE TABLE {tablename}")

        with open(f"avro_backup/{tablename}.avro", "rb") as fo:
            avro_reader = reader(fo)
            list = []

            for record in avro_reader:
                list.append(record)

        df = pd.DataFrame(list)
        write_pandas(conn, df, tablename)

        return 1
    except Exception as e:
        print(e)

        return 0
    finally:
        cs.close()
