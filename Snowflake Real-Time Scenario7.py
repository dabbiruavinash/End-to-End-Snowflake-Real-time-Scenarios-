# Snowflake Automate Data Load & Validation in Single Step

CREATE OR REPLACE PROCEDURE LOAD_AND_VALIDATE()
RETURNS VARCHAR()
LANGUAGE SQL
AS
$$
DECLARE
 
  temp_table_name STRING;
  total_rows_loaded INT DEFAULT 0;
  duplicate_rows INT DEFAULT 0;
  null_rows INT DEFAULT 0;
  status VARCHAR(50);
  error_message VARCHAR();
   result_message STRING;

BEGIN
  temp_table_name := 'TEMP_CUST_DATA';
  status := 'Failed';
  error_message := NULL;

  -- Drop temp table if it exists
  CREATE OR REPLACE TEMPORARY TABLE IDENTIFIER(:temp_table_name) (
  C_CUSTKEY INT,
  C_NAME STRING,
  C_ADDRESS STRING,
  C_NATIONKEY INT,
  C_PHONE STRING,
  C_ACCTBAL INT,
  C_MKTSEGEMENT STRING,
  C_COMMENT STRING);

BEGIN
   -- LOAD DATA INTO TEMPORARY TABLE
   COPY INTO IDENTIFIER(:temp_table_name) from @SOURCE_DATA 
   FILE_FORMAT = (FORMAT_NAME = 'CSVONE')
   ON_ERROR = 'ABORT_STATEMENT';
   
   -- VALIDATE CHECKS
   total_rows_loaded := (SELECT COUNT(*) FROM IDENTIFIER(:temp_table_name));

   null_rows := (SELECT COUNT(*) FROM IDENTIFIER(:temp_table_name) WHERE C_PHONE IS NULL OR C_NATIONKEY IS NULL);

   duplicate_rows := (
   SELECT COUNT(*) FROM (
   SELECT C_CUSTKEY, ROW_NUMBER() OVER (PARTITION BY C_CUSTKEY ORDER BY C_CUSTKEY) AS rn FROM IDENTIFIER(:temp_table_name) a WHERE rn > 1);

   IF (null_row = 0 and duplicate_rows = 0 AND total_rows_loaded > 0) THEN
   INSERT INTO CUSTOMER_DATA(C_CUSTKEY, C_NAME, C_ADDRESS, C_NATIONKEY, C_PHONE, C_ACCTBAL, C_MKTSEGMENT, C_COMMENT)
   SELECT C_CUSTKEY, C_NAME, C_ADDRESS, C_NATIONKEY, C_PHONE, C_ACCTBAL, C_MKTSEGMENT, C_COMMENT FROM IDENTIFIER(:temp_table_name);

   status := 'Success';
   result_message := 'Successfully loaded ' || total_rows_loaded || ' rows with no validation errors.';
 ELSE
   status := 'Failed - Validation Errors';
   error_message := 'Validation failed. ' || null_rows || ' rows with nulls, ' || duplicate_rows || ' duplicate rows found. ' ;
   result_message := error_message;
 END IF;

EXCEPTION
  WHEN OTHER THEN
   status := 'Failed - Execution Error' ;
   error_message := SQLERRM;
   result_message := error_message;
END;

   -- LOG THE OUTCOME ALWAYS
   INSERT INTO AUDIT_LOG (
   status, load_timestamp, rows_loaded, duplicate_rows, null_rows, error_message) values (:status, CURRENT_TIMESTAMP(), :total_rows_loaded, :duplicate_rows, :null_rows, :error_message);

   RETURN 'Procedure execution completed with status: ' || status ||' . Message: ' || result_message;

END;
$$


CALL LOAD_AND_VALIDATE();
