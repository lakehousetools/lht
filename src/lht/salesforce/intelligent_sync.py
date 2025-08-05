import pandas as pd
import time
import requests
import numpy as np
from typing import Optional, Dict, Any, Tuple
from . import query_bapi20, sobjects, sobject_query
from lht.util import merge, field_types


class IntelligentSync:
    """
    Intelligent synchronization system that determines the best method to sync Salesforce data
    based on volume and previous sync status.
    """
    
    def __init__(self, session, access_info: Dict[str, str]):
        """
        Initialize the intelligent sync system.
        
        Args:
            session: Snowflake Snowpark session
            access_info: Dictionary containing Salesforce access details
        """
        self.session = session
        self.access_info = access_info
        
        # Configuration thresholds
        self.BULK_API_THRESHOLD = 10000  # Use Bulk API for records >= this number
        self.REGULAR_API_THRESHOLD = 1000  # Use regular API for records < this number
        self.STAGE_THRESHOLD = 50000  # Use stage for records >= this number
        
    def sync_sobject(self, 
                    sobject: str, 
                    schema: str, 
                    table: str, 
                    match_field: str = 'ID',
                    use_stage: bool = False,
                    stage_name: Optional[str] = None,
                    force_full_sync: bool = False) -> Dict[str, Any]:
        """
        Intelligently sync a Salesforce SObject to Snowflake.
        
        Args:
            sobject: Salesforce SObject name (e.g., 'Account', 'Contact')
            schema: Snowflake schema name
            table: Snowflake table name
            match_field: Field to use for matching records (default: 'ID')
            use_stage: Whether to use Snowflake stage for large datasets
            stage_name: Snowflake stage name (required if use_stage=True)
            force_full_sync: Force a full sync regardless of previous sync status
            
        Returns:
            Dictionary containing sync results and metadata
        """
        print(f"🔄 Starting intelligent sync for {sobject} -> {schema}.{table}")
        
        # Check if table exists and get sync status
        table_exists = self._table_exists(schema, table)
        last_modified_date = None
        
        if table_exists and not force_full_sync:
            last_modified_date = self._get_last_modified_date(schema, table)
            print(f"📅 Last sync date: {last_modified_date}")
        
        # Determine sync strategy
        sync_strategy = self._determine_sync_strategy(
            sobject, table_exists, last_modified_date, use_stage, stage_name
        )
        
        print(f"🎯 Sync strategy: {sync_strategy['method']}")
        print(f"📊 Estimated records: {sync_strategy['estimated_records']}")
        
        # Execute sync based on strategy
        start_time = time.time()
        result = self._execute_sync_strategy(sync_strategy, sobject, schema, table, match_field)
        end_time = time.time()
        
        # Compile results
        sync_result = {
            'sobject': sobject,
            'target_table': f"{schema}.{table}",
            'sync_method': sync_strategy['method'],
            'estimated_records': sync_strategy['estimated_records'],
            'actual_records': result.get('records_processed', 0),
            'sync_duration_seconds': end_time - start_time,
            'last_modified_date': last_modified_date,
            'sync_timestamp': pd.Timestamp.now(),
            'success': result.get('success', False),
            'error': result.get('error', None)
        }
        
        print(f"✅ Sync completed: {sync_result['actual_records']} records in {sync_result['sync_duration_seconds']:.2f}s")
        return sync_result
    
    def _table_exists(self, schema: str, table: str) -> bool:
        """Check if the target table exists in Snowflake."""
        try:
            result = self.session.sql(f"SHOW TABLES LIKE '{table}' IN SCHEMA {schema}").collect()
            return len(result) > 0
        except Exception:
            return False
    
    def _get_last_modified_date(self, schema: str, table: str) -> Optional[pd.Timestamp]:
        """Get the most recent LastModifiedDate from the target table."""
        try:
            query = f"SELECT MAX(LASTMODIFIEDDATE::TIMESTAMP_NTZ) as LAST_MODIFIED FROM {schema}.{table}"
            result = self.session.sql(query).collect()
            
            if result and result[0]['LAST_MODIFIED']:
                return pd.to_datetime(result[0]['LAST_MODIFIED'])
            return None
        except Exception as e:
            print(f"⚠️ Warning: Could not get last modified date: {e}")
            return None
    
    def _determine_sync_strategy(self, 
                               sobject: str, 
                               table_exists: bool, 
                               last_modified_date: Optional[pd.Timestamp],
                               use_stage: bool,
                               stage_name: Optional[str]) -> Dict[str, Any]:
        """
        Determine the best synchronization strategy based on data volume and previous sync status.
        """
        
        # Get estimated record count
        estimated_records = self._estimate_record_count(sobject, last_modified_date)
        
        # Determine sync method
        if not table_exists or last_modified_date is None:
            # First-time sync
            if estimated_records >= self.BULK_API_THRESHOLD:
                method = "bulk_api_full"
                if use_stage and stage_name and estimated_records >= self.STAGE_THRESHOLD:
                    method = "bulk_api_stage_full"
            else:
                method = "regular_api_full"
        else:
            # Incremental sync
            if estimated_records >= self.BULK_API_THRESHOLD:
                method = "bulk_api_incremental"
                if use_stage and stage_name and estimated_records >= self.STAGE_THRESHOLD:
                    method = "bulk_api_stage_incremental"
            else:
                method = "regular_api_incremental"
        
        return {
            'method': method,
            'estimated_records': estimated_records,
            'is_incremental': table_exists and last_modified_date is not None,
            'use_stage': use_stage and stage_name and estimated_records >= self.STAGE_THRESHOLD,
            'stage_name': stage_name if use_stage and stage_name and estimated_records >= self.STAGE_THRESHOLD else None
        }
    
    def _estimate_record_count(self, sobject: str, last_modified_date: Optional[pd.Timestamp]) -> int:
        """Estimate the number of records to be synced."""
        try:
            # Build query to count records
            if last_modified_date:
                # Incremental sync - count records modified since last sync
                lmd_sf = str(last_modified_date)[:10] + 'T' + str(last_modified_date)[11:19] + '.000Z'
                query = f"SELECT COUNT() FROM {sobject} WHERE LastModifiedDate > {lmd_sf}"
            else:
                # Full sync - count all records
                query = f"SELECT COUNT() FROM {sobject}"
            
            # Use regular API for count (faster than Bulk API for counts)
            headers = {
                "Authorization": f"Bearer {self.access_info['access_token']}",
                "Content-Type": "application/json"
            }
            url = f"{self.access_info['instance_url']}/services/data/v58.0/query?q={query}"
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            return result['records'][0]['expr0']
            
        except Exception as e:
            print(f"⚠️ Warning: Could not estimate record count: {e}")
            # Return a conservative estimate
            return 50000 if last_modified_date else 100000
    
    def _execute_sync_strategy(self, 
                             strategy: Dict[str, Any], 
                             sobject: str, 
                             schema: str, 
                             table: str,
                             match_field: str) -> Dict[str, Any]:
        """Execute the determined sync strategy."""
        
        method = strategy['method']
        
        try:
            if method.startswith('bulk_api'):
                return self._execute_bulk_api_sync(strategy, sobject, schema, table)
            elif method.startswith('regular_api'):
                return self._execute_regular_api_sync(strategy, sobject, schema, table, match_field)
            else:
                raise ValueError(f"Unknown sync method: {method}")
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'records_processed': 0
            }
    
    def _execute_bulk_api_sync(self, 
                              strategy: Dict[str, Any], 
                              sobject: str, 
                              schema: str, 
                              table: str) -> Dict[str, Any]:
        """Execute Bulk API 2.0 sync."""
        
        # Get query string and field descriptions
        last_modified_date = None
        if strategy['is_incremental']:
            # Get the last modified date from the existing table
            last_modified_date = self._get_last_modified_date(schema, table)
            if last_modified_date:
                lmd_sf = str(last_modified_date)[:10] + 'T' + str(last_modified_date)[11:19] + '.000Z'
        
        query_string, df_fields = sobjects.describe(self.access_info, sobject, lmd_sf if last_modified_date else None)
        
        # Convert query string to proper SOQL
        soql_query = query_string.replace('+', ' ').replace('select', 'SELECT').replace('from', 'FROM')
        if last_modified_date:
            soql_query = soql_query.replace('where', 'WHERE').replace('LastModifiedDate>', 'LastModifiedDate > ')
        
        print(f"🔍 Executing Bulk API query: {soql_query}")
        
        # Create bulk query job
        job_response = query_bapi20.create_batch_query(self.access_info, soql_query)
        job_id = job_response['id']
        
        print(f"📋 Created Bulk API job: {job_id}")
        
        # Monitor job status
        while True:
            status_response = query_bapi20.query_status(self.access_info, 'QueryAll', job_id)
            if isinstance(status_response, list) and len(status_response) > 0:
                job_status = status_response[0]
            else:
                job_status = status_response
            
            state = job_status['state']
            print(f"📊 Job status: {state}")
            
            if state == 'JobComplete':
                break
            elif state in ['Failed', 'Aborted']:
                raise Exception(f"Bulk API job failed with state: {state}")
            
            time.sleep(10)
        
        # Get results
        use_stage = strategy.get('use_stage', False)
        stage_name = strategy.get('stage_name')
        
        if use_stage and stage_name:
            result = query_bapi20.get_bulk_results_with_stage(
                self.session, self.access_info, job_id, sobject, schema, table,
                stage_name=stage_name, use_stage=True
            )
        else:
            result = query_bapi20.get_bulk_results(
                self.session, self.access_info, job_id, sobject, schema, table
            )
        
        # Clean up job
        try:
            query_bapi20.delete_query(self.access_info, job_id)
            print(f"🧹 Cleaned up job: {job_id}")
        except Exception as e:
            print(f"⚠️ Warning: Could not clean up job {job_id}: {e}")
        
        return {
            'success': True,
            'records_processed': strategy['estimated_records'],
            'job_id': job_id
        }
    
    def _execute_regular_api_sync(self, 
                                 strategy: Dict[str, Any], 
                                 sobject: str, 
                                 schema: str, 
                                 table: str,
                                 match_field: str) -> Dict[str, Any]:
        """Execute regular API sync using sobject_query."""
        
        # Get query string and field descriptions
        last_modified_date = None
        if strategy['is_incremental']:
            last_modified_date = self._get_last_modified_date(schema, table)
            if last_modified_date:
                lmd_sf = str(last_modified_date)[:10] + 'T' + str(last_modified_date)[11:19] + '.000Z'
        
        query_string, df_fields = sobjects.describe(self.access_info, sobject, lmd_sf if last_modified_date else None)
        
        # Convert query string to proper SOQL
        soql_query = query_string.replace('+', ' ').replace('select', 'SELECT').replace('from', 'FROM')
        if last_modified_date:
            soql_query = soql_query.replace('where', 'WHERE').replace('LastModifiedDate>', 'LastModifiedDate > ')
        
        print(f"🔍 Executing regular API query: {soql_query}")
        
        # Execute query and process results
        records_processed = 0
        
        if strategy['is_incremental']:
            # Incremental sync - use merge logic
            tmp_table = f"TMP_{table}"
            self.session.sql(f"CREATE OR REPLACE TEMPORARY TABLE {schema}.{tmp_table} LIKE {schema}.{table}").collect()
            
            # Get table fields
            results = self.session.sql(f"SHOW COLUMNS IN TABLE {schema}.{tmp_table}").collect()
            table_fields = [field[2] for field in results if field[2]]
            
            # Query and load to temp table
            for batch_df in sobject_query.query_records(self.access_info, soql_query):
                if batch_df is not None and not batch_df.empty:
                    # Format data
                    formatted_df = field_types.format_sync_file(batch_df, df_fields)
                    formatted_df = formatted_df.replace(np.nan, None)
                    
                    # Write to temp table
                    self.session.write_pandas(
                        formatted_df, f"{schema}.{tmp_table}", 
                        quote_identifiers=False, auto_create_table=False, 
                        overwrite=False, use_logical_type=True, on_error="CONTINUE"
                    )
                    records_processed += len(batch_df)
            
            # Merge temp table with main table
            if records_processed > 0:
                merge.format_filter_condition(self.session, f"{schema}.{tmp_table}", f"{schema}.{table}", match_field, match_field)
            
        else:
            # Full sync - overwrite table
            for batch_df in sobject_query.query_records(self.access_info, soql_query):
                if batch_df is not None and not batch_df.empty:
                    # Format data
                    formatted_df = field_types.format_sync_file(batch_df, df_fields)
                    formatted_df = formatted_df.replace(np.nan, None)
                    
                    # Write to table (overwrite for first batch, append for subsequent)
                    overwrite = records_processed == 0
                    self.session.write_pandas(
                        formatted_df, f"{schema}.{table}", 
                        quote_identifiers=False, auto_create_table=True, 
                        overwrite=overwrite, use_logical_type=True, on_error="CONTINUE"
                    )
                    records_processed += len(batch_df)
        
        return {
            'success': True,
            'records_processed': records_processed
        }


def sync_sobject_intelligent(session, 
                           access_info: Dict[str, str],
                           sobject: str, 
                           schema: str, 
                           table: str, 
                           match_field: str = 'ID',
                           use_stage: bool = False,
                           stage_name: Optional[str] = None,
                           force_full_sync: bool = False) -> Dict[str, Any]:
    """
    Convenience function for intelligent SObject synchronization.
    
    Args:
        session: Snowflake Snowpark session
        access_info: Dictionary containing Salesforce access details
        sobject: Salesforce SObject name (e.g., 'Account', 'Contact')
        schema: Snowflake schema name
        table: Snowflake table name
        match_field: Field to use for matching records (default: 'ID')
        use_stage: Whether to use Snowflake stage for large datasets
        stage_name: Snowflake stage name (required if use_stage=True)
        force_full_sync: Force a full sync regardless of previous sync status
        
    Returns:
        Dictionary containing sync results and metadata
    """
    sync_system = IntelligentSync(session, access_info)
    return sync_system.sync_sobject(
        sobject, schema, table, match_field, use_stage, stage_name, force_full_sync
    ) 