// CsvTableWindowController.cs
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UIElements;

public sealed class CsvTableWindowController : WindowController
{
    [Tooltip("CSV file name without .csv under Assets/Resources/tables/")]
    [SerializeField] private string csvName = "parts";

    private string[] headers;
    private List<string[]> rows;
    private MultiColumnListView table;

    protected override void OnWindowCreated()
    {
        Debug.Log("[CsvTable] OnWindowCreated called");

        LoadCsv(csvName);
        Debug.Log($"[CsvTable] Loaded CSV '{csvName}': {headers.Length} columns, {rows.Count} rows");

        BuildTable();
    }

    #region CSV Loading
    private void LoadCsv(string name)
    {
        var ta = Resources.Load<TextAsset>($"tables/{name}");
        if (ta == null)
        {
            Debug.LogError($"[CsvTable] CSV not found: Resources/tables/{name}.csv");
            headers = Array.Empty<string>();
            rows = new List<string[]>();
            return;
        }

        var lines = ta.text
                      .Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries);

        headers = lines[0].Split(',');
        rows = lines.Skip(1)
                       .Select(l => l.Split(','))
                       .ToList();
    }
    #endregion

    #region Table Building
    private void BuildTable()
    {
        // 1) Gather your data
        //    You might already have these from LoadCsv(...)
        string[] headers = this.headers;
        List<string[]> rows = this.rows;

        // 2) Create the table in one line
        var table = TableBuilder.CreateTable(headers, rows);

        // 3) Insert into your placeholder
        var slot = windowRoot.Q<VisualElement>("window-content");
        if (slot == null)
        {
            Debug.LogError("Couldn't find 'window-content'");
            return;
        }
        slot.Add(table);

        // 4) Make sure it draws immediately
        table.Rebuild();
    }
    #endregion
}
