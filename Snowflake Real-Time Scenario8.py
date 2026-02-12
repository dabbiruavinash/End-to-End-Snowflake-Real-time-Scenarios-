# Snowpipe + Dynamic Table + Alerts

CREATE OR REPLACE SCHEMA PIPELINE;

--We are manually putting file but you can easily implement the 

-- Create Customer Table
CREATE OR REPLACE TABLE STG_Customer (
    CUST_ID STRING,
    CUST_NAME STRING,
    OUTSTANDING_AMT NUMBER,
    CRID STRING,
    LOCATION STRING,
    CUST_CREATED DATE);

-- Insert Data
INSERT INTO STG_Customer (CUST_ID, CUST_NAME, OUTSTANDING_AMT, CRID, LOCATION, CUST_CREATED) VALUES
('C-101', 'Raman', 500, 'ABVC', 'LA', '2025-08-11'),
('C-101', 'Raman', 500, 'ABVC', 'LA', '2025-08-12'), -- in the cleansed layer we should have latest record
('C-102', 'Rahul', 200, 'XYZ', 'AF', '2025-08-14'),
('C-103', 'Anshi', 5000, 'MNCD', 'GA', '2025-08-15');



CREATE OR REPLACE TABLE ITEM (
    CUST_ID STRING,
    ITEM_ID STRING,
    ITEM_CATEGORY STRING,
    ITEM_STATUS STRING,
    COUNTS NUMBER,
    PRICE NUMBER);


INSERT INTO ITEM (CUST_ID, ITEM_ID, ITEM_CATEGORY, ITEM_STATUS, COUNTS, PRICE) VALUES
('C-101', 'a-101', 'Printer', 'Active', 1, 100),
('C-101', 'a-101', 'Printer', 'Active', 4, 200),-- this row should be there 
('C-102', 'a-103', 'Ink', 'Active', 2, 300),
('C-103', 'a-103', 'Ribbon', 'Active', 3, 100),
('C-103', 'a-103', 'Ribbon', 'Active', 2, 200); -- We need this row as this is highest price 


SELECT * FROM ITEM;

-- LET'S WORK ON CLEANED LAYER

CREATE OR REPLACE DYNAMIC TABLE CUSTOMER_DT
 TARGET_LAG = DOWNSTREAM
 WAREHOUSE = COMPUTE_WH
 INITIALIZE = ON_CREATE
AS
 select * from STG_CUSTOMER qualify row_number() over (partition by cust_id order by cust_created desc) = 1;
 select * from CUSTOMER_DT;

CREATE OR REPLACE DYNAMIC TABLE ITEM_DT
 TARGET_LAG = DOWNSTREAM
 WAREHOUSE = COMPUTE_WH
 --INITIALIZE = ON_SCHEDULE

AS
 SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY CUST_ID ORDER BY PRICE DESC) AS rn FROM ITEM) t WHERE rn = 1;

SELECT * FROM ITEM_DT;

-- FINAL DYNAMIC TABLE WHERE WE WILL BE CALCULATING PRICE PER ITEM BY DIVIDING PRICE/COUNT

CREATE OR REPLACE DYNAMIC TABLE CUST_ITEM_DT
 TARGET_LAG = '1 MINUTES'
 WAREHOUSE = COMPUTE_WH
AS
 select c.cust_id, c.cust_name, c.crid, c.location, c.cust_created, a.item_id, a.item_category, a.item_status, a.price, a.counts, ROUND(a.price/a.count, 2) AS Price_Per_item from CUSTOMER_DT c, ITEM_DT a where c.cust_id = a.cust_id;

 select * from CUST_ITEM_DT;

-- Inserting few more records, assuming these will coming from customer S3 bucket 

INSERT INTO STG_CUSTOMER (CUST_ID, CUST_NAME, OUTSTANDING_AMT, CRID, LOCATION, CUST_CREATED)
VALUES 
('c-102', 'Megan', 3500, 'XYAZ', 'AF', '2023-08-15'),
('c-104', 'Vincet', 5000, 'ABDF', 'TX', '2023-08-15');


INSERT INTO ITEM (CUST_ID, ITEM_ID, ITEM_CATEGORY, ITEM_STATUS, COUNTS, PRICE)
VALUES 
('c-104', 'a-104', 'Oil', 'Active', 0, 500);

CREATE OR REPLACE NOTIFICATION INTEGRATION DT_FAILURE_ALERT
TYPE = EMAIL
ENABLED = TRUE
ALLOWED_RECEPIENTS = ('avinashdvvss@gmail.com')
COMMENT = 'Snowflake Dynamic Table Refresh Notification' ;

CREATE OR REPLACE ALERT DT_FAILURE
WAREHOUSE = COMPUTE_WH
SCHEDULE = '1 MINUTE'
IF (EXISTS (
Select * from table(information_schema.DYNAMIC_TABLE_REFRESH_HISTORY(DATA_TIMESTAMP_START => dateadd('hour', -1, current_timestamp()), DATA_TIMESTAMP_END => dateadd('hour', 0 , current_timestamp()), NAME => 'CUST_ITEM_DT', ERROR_ONLY => TRUE)) ORDER BY name, date_timestamp))
Then CALL system$send_email('DT_FAILURE_ALERT', 'emailid', 'Dynamic Table failure Notification', 'Issue with some data, Main Error {Division by Zero}');

-- this is to check dynamic table history

select * from table(information_schema.DYNAMIC_TABLE_REFRESH_HISTORY(DATA_TIMESTAMP_START => dateadd('hour', -1, current_timestamp()), DATA_TIMESTAMP_END => dateadd('hour', 0 ,current_timestamp()), NAME => 'CUST_ITEM_DT', ERROR_ONLY => TRUE));

ALTER ALERT DT_FAILURE RESUME;

 