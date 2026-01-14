"""
Simplified CSV Tools for local LLM compatibility.
These tools have flat parameter structures that are easier for local LLMs to handle.
"""
from typing import Any, Dict, List, Optional
import pandas as pd
import os
import logging
from agno.tools import Toolkit

logger = logging.getLogger(__name__)


class SimpleCsvTools(Toolkit):
    """
    Simplified CSV analysis tools designed for local LLM compatibility.
    Uses flat parameter structures instead of nested dicts.
    """
    
    def __init__(self, base_dir: str = "", **kwargs):
        self.base_dir = base_dir
        self.dataframes: Dict[str, pd.DataFrame] = {}
        
        tools: List[Any] = [
            self.list_csv_files,
            self.load_csv_file,
            self.show_columns,
            self.show_head,
            self.show_stats,
            self.query_data,
            self.get_column_values,
            self.groupby_sum,
            self.groupby_mean,
            self.groupby_count,
            self.filter_data,
            self.sort_data,
            self.value_counts,
            self.correlation,
        ]
        
        super().__init__(name="csv_tools", tools=tools, **kwargs)
    
    def list_csv_files(self) -> str:
        """
        List all available CSV files that can be analyzed.
        
        Returns:
            List of available CSV filenames (without full paths for security)
        """
        try:
            if not self.base_dir or not os.path.isdir(self.base_dir):
                return "Error: No CSV directory configured."
            
            files = [f for f in os.listdir(self.base_dir) if f.lower().endswith('.csv')]
            
            if not files:
                return "No CSV files found. Please upload a CSV file first."
            
            return f"Available CSV files: {', '.join(files)}"
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return f"Error listing files: {str(e)}"
    
    def load_csv_file(self, filename: str, dataframe_name: str = "data") -> str:
        """
        Load a CSV file into memory for analysis.
        
        Args:
            filename: The name of the CSV file (e.g., "sales.csv") - NOT the full path!
            dataframe_name: A name to reference this data later (default: "data")
        
        Returns:
            Success message with row/column count, or error message
        """
        try:
            # Construct full path internally (user never sees it)
            file_path = os.path.join(self.base_dir, filename)
            
            logger.info(f"Loading CSV: {filename} as '{dataframe_name}'")
            df = pd.read_csv(file_path)
            self.dataframes[dataframe_name] = df
            return f"Successfully loaded '{filename}' as '{dataframe_name}' with {len(df)} rows and {len(df.columns)} columns. Columns: {', '.join(df.columns.tolist())}"
        except FileNotFoundError:
            return f"Error: File '{filename}' not found. Use list_csv_files to see available files."
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            return f"Error loading CSV: {str(e)}"
    
    def load_csv(self, file_path: str, dataframe_name: str = "data") -> str:
        """
        [DEPRECATED - use load_csv_file instead]
        Load a CSV file using full path.
        
        Args:
            file_path: The FULL ABSOLUTE PATH to the CSV file
            dataframe_name: A name to reference this data later (default: "data")
        
        Returns:
            Success message with row/column count, or error message
        """
        try:
            logger.info(f"Loading CSV: {file_path} as '{dataframe_name}'")
            df = pd.read_csv(file_path)
            self.dataframes[dataframe_name] = df
            return f"Successfully loaded '{dataframe_name}' with {len(df)} rows and {len(df.columns)} columns. Columns: {', '.join(df.columns.tolist())}"
        except FileNotFoundError:
            return f"Error: File not found. Use list_csv_files to see available files."
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            return f"Error loading CSV: {str(e)}"
    
    def show_columns(self, dataframe_name: str = "data") -> str:
        """
        Show all column names in the loaded dataframe.
        
        Args:
            dataframe_name: Name of the dataframe to inspect (default: "data")
        
        Returns:
            List of column names or error message
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        cols_info = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            cols_info.append(f"- {col} ({dtype})")
        return f"Columns in '{dataframe_name}':\n" + "\n".join(cols_info)
    
    def show_head(self, dataframe_name: str = "data", rows: int = 5) -> str:
        """
        Show the first few rows of the dataframe.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            rows: Number of rows to show (default: 5)
        
        Returns:
            Markdown table of the first rows
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        return df.head(rows).to_markdown(index=False)
    
    def show_stats(self, dataframe_name: str = "data") -> str:
        """
        Show summary statistics for numeric columns.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
        
        Returns:
            Statistics including count, mean, std, min, max for numeric columns
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        try:
            stats = df.describe().to_markdown()
            return f"Statistics for '{dataframe_name}':\n{stats}"
        except Exception as e:
            return f"Error computing statistics: {str(e)}"
    
    def query_data(self, dataframe_name: str = "data", operation: str = "", column: str = "") -> str:
        """
        Perform a simple operation on the data.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            operation: One of: "sum", "mean", "count", "min", "max", "unique", "median", "std"
            column: The column name to operate on (required for sum, mean, min, max)
        
        Returns:
            Result of the operation
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            if operation == "count":
                return f"Total rows: {len(df)}"
            elif operation == "sum" and column:
                result = df[column].sum()
                return f"Sum of {column}: {result}"
            elif operation == "mean" and column:
                result = df[column].mean()
                return f"Mean of {column}: {result:.2f}"
            elif operation == "median" and column:
                result = df[column].median()
                return f"Median of {column}: {result}"
            elif operation == "std" and column:
                result = df[column].std()
                return f"Standard deviation of {column}: {result:.2f}"
            elif operation == "min" and column:
                result = df[column].min()
                return f"Min of {column}: {result}"
            elif operation == "max" and column:
                result = df[column].max()
                return f"Max of {column}: {result}"
            elif operation == "unique" and column:
                unique_vals = df[column].unique().tolist()
                if len(unique_vals) > 20:
                    return f"Unique values in {column}: {unique_vals[:20]} ... (showing first 20 of {len(unique_vals)})"
                return f"Unique values in {column}: {unique_vals}"
            else:
                return f"Unknown operation '{operation}'. Use: sum, mean, median, std, count, min, max, unique"
        except KeyError:
            return f"Error: Column '{column}' not found. Available columns: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def get_column_values(self, dataframe_name: str = "data", column: str = "", limit: int = 10) -> str:
        """
        Get values from a specific column.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            column: The column to get values from
            limit: Maximum number of values to return (default: 10)
        
        Returns:
            List of values from the column
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            values = df[column].head(limit).tolist()
            return f"First {limit} values in '{column}': {values}"
        except KeyError:
            return f"Error: Column '{column}' not found. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def groupby_sum(self, dataframe_name: str = "data", group_by_column: str = "", sum_column: str = "", limit: int = 20) -> str:
        """
        Group data by a column and sum another column.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            group_by_column: The column to group by (e.g., "Category")
            sum_column: The column to sum (e.g., "Sales")
            limit: Maximum number of results to return (default: 20)
        
        Returns:
            Grouped sum results as markdown table
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            result = df.groupby(group_by_column)[sum_column].sum().reset_index()
            result = result.sort_values(sum_column, ascending=False).head(limit)
            return f"Sum of '{sum_column}' grouped by '{group_by_column}':\n{result.to_markdown(index=False)}"
        except KeyError as e:
            return f"Error: Column not found - {e}. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def groupby_count(self, dataframe_name: str = "data", group_by_column: str = "", limit: int = 20) -> str:
        """
        Group data by a column and count occurrences.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            group_by_column: The column to group by (e.g., "Category")
            limit: Maximum number of results to return (default: 20)
        
        Returns:
            Grouped count results as markdown table
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            result = df.groupby(group_by_column).size().reset_index(name='count')
            result = result.sort_values('count', ascending=False).head(limit)
            return f"Count grouped by '{group_by_column}':\n{result.to_markdown(index=False)}"
        except KeyError as e:
            return f"Error: Column not found - {e}. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def filter_data(self, dataframe_name: str = "data", column: str = "", operator: str = "", value: str = "", limit: int = 20) -> str:
        """
        Filter data based on a condition.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            column: The column to filter on
            operator: One of: "equals", "not_equals", "greater", "less", "contains"
            value: The value to compare against (will be auto-converted to number if numeric)
            limit: Maximum number of rows to return (default: 20)
        
        Returns:
            Filtered rows as markdown table
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            # Try to convert value to number if possible
            try:
                numeric_value = float(value)
            except (ValueError, TypeError):
                numeric_value = None
            
            if operator == "equals":
                if numeric_value is not None:
                    filtered = df[df[column] == numeric_value]
                else:
                    filtered = df[df[column] == value]
            elif operator == "not_equals":
                if numeric_value is not None:
                    filtered = df[df[column] != numeric_value]
                else:
                    filtered = df[df[column] != value]
            elif operator == "greater":
                filtered = df[df[column] > (numeric_value if numeric_value is not None else value)]
            elif operator == "less":
                filtered = df[df[column] < (numeric_value if numeric_value is not None else value)]
            elif operator == "contains":
                filtered = df[df[column].astype(str).str.contains(value, case=False, na=False)]
            else:
                return f"Unknown operator '{operator}'. Use: equals, not_equals, greater, less, contains"
            
            count = len(filtered)
            result = filtered.head(limit)
            return f"Found {count} rows where {column} {operator} '{value}':\n{result.to_markdown(index=False)}"
        except KeyError:
            return f"Error: Column '{column}' not found. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def sort_data(self, dataframe_name: str = "data", column: str = "", ascending: bool = True, limit: int = 20) -> str:
        """
        Sort data by a column.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            column: The column to sort by
            ascending: Sort ascending if True, descending if False (default: True)
            limit: Maximum number of rows to return (default: 20)
        
        Returns:
            Sorted rows as markdown table
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            sorted_df = df.sort_values(column, ascending=ascending).head(limit)
            direction = "ascending" if ascending else "descending"
            return f"Top {limit} rows sorted by '{column}' ({direction}):\n{sorted_df.to_markdown(index=False)}"
        except KeyError:
            return f"Error: Column '{column}' not found. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def value_counts(self, dataframe_name: str = "data", column: str = "", limit: int = 20) -> str:
        """
        Count occurrences of each unique value in a column.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            column: The column to count values in
            limit: Maximum number of results to return (default: 20)
        
        Returns:
            Value counts as markdown table
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            counts = df[column].value_counts().head(limit).reset_index()
            counts.columns = [column, 'count']
            return f"Value counts for '{column}':\n{counts.to_markdown(index=False)}"
        except KeyError:
            return f"Error: Column '{column}' not found. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def groupby_mean(self, dataframe_name: str = "data", group_by_column: str = "", mean_column: str = "", limit: int = 20) -> str:
        """
        Group data by a column and calculate the average of another column.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            group_by_column: The column to group by (e.g., "Category")
            mean_column: The column to average (e.g., "Price")
            limit: Maximum number of results to return (default: 20)
        
        Returns:
            Grouped average results as markdown table
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            result = df.groupby(group_by_column)[mean_column].mean().reset_index()
            result = result.sort_values(mean_column, ascending=False).head(limit)
            result[mean_column] = result[mean_column].round(2)
            return f"Average of '{mean_column}' grouped by '{group_by_column}':\n{result.to_markdown(index=False)}"
        except KeyError as e:
            return f"Error: Column not found - {e}. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"

    def correlation(self, dataframe_name: str = "data", column1: str = "", column2: str = "") -> str:
        """
        Calculate the correlation between two numeric columns.
        
        Args:
            dataframe_name: Name of the dataframe (default: "data")
            column1: First numeric column
            column2: Second numeric column
        
        Returns:
            Correlation coefficient with interpretation
        """
        if dataframe_name not in self.dataframes:
            return f"Error: No dataframe named '{dataframe_name}'. Use load_csv first."
        
        df = self.dataframes[dataframe_name]
        
        try:
            corr = df[column1].corr(df[column2])
            
            # Interpret the correlation
            if abs(corr) >= 0.7:
                strength = "strong"
            elif abs(corr) >= 0.4:
                strength = "moderate"
            else:
                strength = "weak"
            
            direction = "positive" if corr > 0 else "negative"
            
            return f"Correlation between '{column1}' and '{column2}': {corr:.3f} ({strength} {direction} correlation)"
        except KeyError as e:
            return f"Error: Column not found - {e}. Available: {', '.join(df.columns.tolist())}"
        except Exception as e:
            return f"Error: {str(e)}"
