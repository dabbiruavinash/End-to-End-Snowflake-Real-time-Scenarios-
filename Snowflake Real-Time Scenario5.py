# Dynamic Table Creation from CSV File Headers

CREATE OR REPLACE PROCEDURE CREATE_DYNAMIC_TABLE_FROM_HEADER()
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    file_name STRING;
	table_name STRING;
    header_line STRING;
	column_list ARRAY;
	column_count INT;
    column_definitions STRING DEFAULT '';
    i INT DEFAULT 0;
    col_def STRING;      
    create_table_sql STRING;
    copy_into_sql STRING;
	
BEGIN
    -- Step 1: Get the file name from the @HEADER stage
    
    SELECT RELATIVE_PATH     INTO file_name     FROM DIRECTORY(@HEADER);

    -- Step 2: Determine the table name from the file name (e.g., 'customerheader.csv' -> 'CUSTOMERHEADER')
     table_name := UPPER(STRTOK(file_name, '.', 1));

    -- Step 3: Read the header line into a temporary table
    
    EXECUTE IMMEDIATE '
        CREATE OR REPLACE TEMP TABLE TMP_HEADER_LINE AS
        SELECT $1 AS HEADER_LINE
        FROM @HEADER/' || file_name || '
        (FILE_FORMAT => (CSVTYPE)) 
        LIMIT 1
    ';

    -- Step 4: Read the header line into a variable
    SELECT HEADER_LINE INTO header_line FROM TMP_HEADER_LINE;

    -- Step 5: Parse the header line to get individual column names
	
    column_list := SPLIT(header_line, '|');
	
	--- In this we gonna find the size of array to know how many columns are there/ to iterate 
    column_count := ARRAY_SIZE(column_list); --6

    -- Step 6: Build the column definitions string for CREATE TABLE statement
    -- FOr that we have to Iterate through the column names and data type defined as STRING type
	
    WHILE (i < column_count) DO
        BEGIN
            LET col_name := TRIM(column_list[i]); -- Trim spaces from column names Cust_id
            col_def := '"' || col_name || '" STRING'; -- Enclose column names in double quotes for safety  
 
            IF (i > 0) THEN -- Add comma separator for all columns after the first one
                column_definitions := column_definitions || ', ';
            END IF;

            column_definitions := column_definitions || col_def;
            i := i + 1;
        END;
    END WHILE;

    -- Step 7: Create the new table dynamically
    create_table_sql := 'CREATE OR REPLACE TABLE "' || table_name || '" (' || column_definitions || ')';
    EXECUTE IMMEDIATE create_table_sql;

    -- Step 8: Load data into the newly created table
    
    copy_into_sql := 'COPY INTO "' || table_name || '" FROM @HEADER/' || file_name || ' FILE_FORMAT = (TYPE = CSV, FIELD_DELIMITER = '','', SKIP_HEADER = 1)';
    EXECUTE IMMEDIATE copy_into_sql;

    RETURN 'Table "' || table_name || '" created successfully and data also get loaded successfully from file "' || file_name || '".';
END;
$$;

CALL CREATE_DYNAMIC_TABLE_FROM_HEADER();


DROP TABLE CUSTOMERHEADER;

Select * from Customerheader;