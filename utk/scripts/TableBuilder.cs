using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UIElements;

/// <summary>
/// Utility to build a styled, sortable MultiColumnListView from arbitrary headers and row data.
/// </summary>
public static class TableBuilder
{
    /// <summary>
    /// Creates a MultiColumnListView with given headers and rows, fully configured.
    /// </summary>
    /// <param name="headers">Array of column header titles.</param>
    /// <param name="rows">List of string arrays, each representing a row.</param>
    /// <returns>A configured MultiColumnListView instance.</returns>
    public static MultiColumnListView CreateTable(string[] headers, List<string[]> rows)
    {
        var table = new MultiColumnListView
        {
            fixedItemHeight = 24,
            virtualizationMethod = CollectionVirtualizationMethod.FixedHeight,
            showAlternatingRowBackgrounds = AlternatingRowBackground.All,
            showBorder = true,
            selectionType = SelectionType.Single,
            sortingMode = ColumnSortingMode.Custom,
            style = { flexGrow = 1 }
        };

        // Root class for USS
        table.AddToClassList("csv-table");

        // Define columns based on headers
        for (int c = 0; c < headers.Length; c++)
        {
            int capturedIndex = c;
            var column = new Column
            {
                title = headers[c],
                width = 120,
                sortable = true,
                makeCell = () =>
                {
                    var cell = new Label();
                    cell.AddToClassList("csv-cell");
                    return cell;
                },
                bindCell = (ve, rowIndex) =>
                {
                    ((Label)ve).text = rows[rowIndex][capturedIndex];
                }
            };
            table.columns.Add(column);
        }

        // Assign data source
        table.itemsSource = rows;

        // Sorting logic
        table.columnSortingChanged += () =>
        {
            Debug.Log("[CsvTable] columnSortingChanged fired");

            var sorted = table.sortedColumns;   // IList<SortColumnDescription> or IEnumerable
            if (sorted == null || !sorted.Any())
            {
                Debug.Log("[CsvTable] No sorted columns, aborting");
                return;
            }

            var desc = sorted.First();        // primary sort
            int colIdx = desc.columnIndex;
            bool asc = desc.direction == SortDirection.Ascending;
            Debug.Log($"[CsvTable] Sorting by col {colIdx}, asc={asc}");

            rows.Sort((a, b) =>
            {
                int cmp = StringComparer.OrdinalIgnoreCase.Compare(a[colIdx], b[colIdx]);
                return asc ? cmp : -cmp;
            });

            table.Rebuild();
            Debug.Log("[CsvTable] Table rebuilt after sort");
        };

        // 5) Hook selection change
        table.selectionChanged += selectedItems =>
        {
            // selectedItems is IEnumerable<object>, where each object is your string[] row
            var row = selectedItems.Cast<string[]>().FirstOrDefault();
            if (row != null)
            {
                Debug.Log($"[CsvTable] Row selected: {string.Join(", ", row)}");
            }
        };

        return table;
    }
}
