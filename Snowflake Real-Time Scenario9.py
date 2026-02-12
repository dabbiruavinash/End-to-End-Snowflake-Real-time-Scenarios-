# Load Excel Files into Snowflake Using Snowpark

CREATE OR REPLACE PROCEDURE LOAD_EXCEL_FILES(file_name STRING, target_table STRING)
RETURN STRING
LANGUAGE PYTHON
RUNTIME_VERSIOIN = '3.9'
PACKAGE = ('snowflake-snowpark-python', 'pandas', 'openpyxl')
HANDLER = 'main'
AS
$$
import pandas as pd
from snowflake.snowpark import Session
import traceback

def main(session: Session, file_name: str, target_table: str) -> str:
   try:
       # Get file from stage
       file_path = f"@EXCEL_DATA/{file_name}"
       session.file.get(file_path,'/tmp')
       local_path = f"/tmp/{file_name}"

       # Read Excel into pandas dataframe
       panda_df = pd.read_excel(local_path)

       # Convert pandas dataframe to snowpark dataframe
       snow_df = session.create_dataframe(panda_df)

       try:
            # Write dataframe to snowflake table
            snow_df.write.save_as_table(target_table, mode = "overwrite")

            # log success with row count
             row_count = len(panda_df)
             log_status(session, file_name, target_table, "SUCCESS", None, row_count)
                  return f"{row_count} rows into table '{target_table}' Loaded Successfully"

        except Exception as e:
             # log failure if table write fails
             log_status(session, file_name, target_table, "FAILED", str(e), 0)
                  return f"Failed to write table: {e}"

        except Exception as e:
             # log top-level failure
             log_status(session, file_name, target_table, "FAILED", traceback.format_exc()[:1500], 0)
                  return f"Procedure could not execute. Error: {str(e)}"

def log_status(session, file_name, target_table, status, error_message=None, row_count=0):
    try:
        insert_stmt = f"""
            INSERT INTO EXCEL_LOAD_LOGS (
                FILE_NAME, TARGET_TABLE, STATUS, ERROR_MESSAGE, ROW_COUNT, ETL_LOAD_TIME
            )
            VALUES (
                '{file_name}',
                '{target_table}',
                '{status}',
                {'NULL' if error_message is None else "'" + error_message.replace("'", "''") + "'"},
                {row_count},
                CURRENT_TIMESTAMP()
            )
        """
        session.sql(insert_stmt).collect()
    except Exception as log_err:
        print("Log insert failed:", log_err)
$$;