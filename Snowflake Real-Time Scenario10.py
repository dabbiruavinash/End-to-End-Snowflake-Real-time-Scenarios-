import snowflake.snowpark as snowpark
from snowflake.snowpark.functions import col

def main(session: snowpark.Session) -> str:
    stage = "@S3_STAGE"
    file_format = "csv_format"
    created_tables = []
    log_messages = []  # To store all messages for final output

    # List all files from the stage
    stage_files_df = session.sql(f"LIST {stage}").collect()

    # check already loaded files from Audit table
    loaded_files_df = session.table("LOG_TABLE").select("FILE_NAME").collect()
    
    already_loaded_files = {row["FILE_NAME"] for row in loaded_files_df}

    
    for row in stage_files_df:
        file_path = row['name']  # e.g., s3://bucket/folder/file.csv

        #if files are already loaded then we gonna skip those files here
        if file_path in already_loaded_files:
            msg = f"Skipping already loaded file: {file_path}"
            print(msg)
            log_messages.append(msg)
            continue


        #get the complete file path here and then split based on / 
        print(f"File path: {file_path}")
        parts = file_path.split('/')

        # extracting folder , file name and setting folder=tablename
        if len(parts) > 1:
            folder = parts[-2]
            file_name = parts[-1]
            table_name = folder.upper()

            #setting up complete path which will be using during copy into load
            full_path = f"{stage}/{folder}/{file_name}"
            print(f"File path in stage: {full_path}")

            # Check if table already exists
            exists_result = session.sql(f"""
                SELECT COUNT(*) AS count 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = '{table_name}' 
                AND TABLE_SCHEMA = CURRENT_SCHEMA()
            """).collect()
            
            exists = int(exists_result[0]['COUNT']) if exists_result else 0

            if exists == 0:
                # Create Automatica table using INFER_SCHEMA
                create_table_sql = f"""
                    CREATE OR REPLACE TABLE {table_name}
                    USING TEMPLATE (
                        SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
                        FROM TABLE(
                            INFER_SCHEMA(LOCATION => '{stage}/{folder}/', FILE_FORMAT => '{file_format}')
                        )
                    )
                """
                print(f"Executing CREATE TABLE SQL: {create_table_sql.strip()}")
                session.sql(create_table_sql).collect()
                created_tables.append(table_name)
                log_messages.append(f"Created new table: {table_name}")

            # next step is to load data into table using COPY INTO command 
            copy_sql = f"""
                COPY INTO {table_name}
                FROM {full_path}
                FILE_FORMAT = (FORMAT_NAME = '{file_format}')
                MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
                ON_ERROR = ABORT_STATEMENT
            """
            session.sql(copy_sql).collect()
            log_messages.append(f"Loaded data into table: {table_name} from {file_name}")

            # Add those processed files into Log file so that we can skip next time 
            session.sql(f"""
                INSERT INTO LOG_TABLE (FOLDER_NAME, FILE_NAME)
                VALUES ('{folder}', '{file_path}')
            """).collect()
            log_messages.append(f"Logged file: {file_path}")

    # If no new tables or data were processed
    if not log_messages:
        log_messages.append("No new files processed. All files were already loaded.")

    # Combine messages into a single result string
    message = "\n".join(log_messages)
    print("Final Result:\n", message)

    return session.create_dataframe([[message]], schema=["RESULT"])