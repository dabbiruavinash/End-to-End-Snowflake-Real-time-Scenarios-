CREATE OR REPLACE SCHEMA BRONZE;

SHOW TABLES;

SHOW INTEGRATIONS;

CREATE OR REPLACE FILE FORMAT CSVONE CLONE RAWLAYER.CSVTYPE;

CREATE OR REPLACE STORAGE INTEGRATION DYNAMIC_INT
TYPE = EXTERNAL_STAGE
ENABLED=TRUE
STORAGE_PROVIDER = 'S3'
STORAGE_AWS_ROLE_ARN = 'Replace ARN'
STORAGE_ALLOWED_LOCATIONS =('s3://realtimeproject-snowflake/');

DESC STORAGE INTEGRATION DYNAMIC_INT;



CREATE OR ALTER STAGE DYNAMICLOAD
FILE_FORMAT=CSVONE
STORAGE_INTEGRATION=DYNAMIC_INT
URL='s3://realtimeproject-snowflake/'
DIRECTORY=(ENABLE=true
AUTO_REFRESH = TRUE) ;

DESC STAGE DYNAMICLOAD;

LIST @DYNAMICLOAD;


SELECT RELATIVE_PATH FROM DIRECTORY(@DYNAMICLOAD);

ALTER STAGE DYNAMICLOAD
REFRESH;

--step 1 create audit table

CREATE OR REPLACE TABLE FILE_LOAD_LOG (
    FILE_NAME STRING,
    LOAD_TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);





--- Create proc to automate all this 

CREATE OR REPLACE PROCEDURE DYNAMIC_TABLE_LOAD()
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    
    file_path STRING;
    folder_name STRING;
    tablename STRING;
    file_name STRING;
    full_stage_path STRING;
    record_count INTEGER;
    file_cursor CURSOR FOR SELECT RELATIVE_PATH FROM DIRECTORY(@DYNAMICLOAD); --- Cursor declaration to get all path and iterate through folders

BEGIN
    -- Loop through each file record returned by the DIRECTORY table function
    FOR file_rec IN file_cursor DO
        file_path := file_rec.RELATIVE_PATH;  --> file_path =CUSTOMER/CUSTOMERS.csv

        --Now Extract the folder name from the file path, this same we will use for Tablename.
          folder_name := SPLIT_PART(file_path, '/', 1);

        -- Extract the file names to check which all files have been processed or not 
         file_name := SPLIT_PART(file_path,'/',2);

        
       
        -- We use a COUNT(*) > 0 pattern to Check if the file has already been processed or not.
        
        SELECT COUNT(1) INTO :record_count FROM FILE_LOAD_LOG WHERE FILE_NAME = :file_path;
        IF (record_count > 0) THEN
            -- If the file is already logged, skip to the next file in the loop
            CONTINUE;
        END IF;
        
        -- Prepare the table name identifier and the full stage path for the current file
        
        tablename := UPPER(folder_name);
        
        full_stage_path := '@DYNAMICLOAD/' || file_path;

        -- Check if the target table already exists in the current schema
        SELECT COUNT(1) INTO :record_count 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = CURRENT_SCHEMA() 
          AND TABLE_NAME = :tablename;

        IF (record_count = 0) THEN
            -- If the table does not exist, create it by inferring the schema from the file.
            -- We use IDENTIFIER(?) and bind variables with USING() for safety and clarity.
            -- NOTE: This assumes a named file format 'CSVONE' already exists in your database.
            LET create_sql := '
                CREATE OR REPLACE TABLE IDENTIFIER(?)
                USING TEMPLATE (
                    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
                    FROM TABLE(
                        INFER_SCHEMA(
                            LOCATION => ?,
                            FILE_FORMAT => ''CSVONE'',
                            IGNORE_CASE => TRUE
                        )
                    )
                )';
            EXECUTE IMMEDIATE create_sql USING (tablename, full_stage_path);
        END IF;

        -- Load the data from the file into the target table.
        -- Set the copy paramters based on your requirements
        
        LET copy_sql := '
            COPY INTO IDENTIFIER(?)
            FROM ?
            FILE_FORMAT = (FORMAT_NAME = ''CSVONE'')
            MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
            ON_ERROR = ''SKIP_FILE''';
        EXECUTE IMMEDIATE copy_sql USING (tablename, full_stage_path);

        -- Now we need to make entry for every file in Audit table 
        
        INSERT INTO FILE_LOAD_LOG (FILE_NAME) VALUES (:file_path);

    END FOR;

    RETURN 'Dynamic ingestion from S3 to Snowflake complete.';
END;
$$;


CALL DYNAMIC_TABLE_LOAD();



SHOW TABLES;

Select * from FILE_LOAD_LOG;