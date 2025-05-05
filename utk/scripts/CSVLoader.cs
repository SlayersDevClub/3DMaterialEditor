using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

static class CsvLoader
{
    public struct Table
    {
        public string[] Headers;
        public List<List<string>> Rows;
    }

    public static Table Load(string resourcePath)
    {
        // CSV in Resources/tables/, omit “.csv”
        var asset = Resources.Load<TextAsset>($"tables/{resourcePath}");
        if (asset == null)
            throw new Exception($"CSV not found: tables/{resourcePath}");
        var lines = asset.text
                         .Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries);

        var headers = lines[0].Split(',');
        var rows = lines
            .Skip(1)
            .Select(l => l.Split(',').ToList())
            .ToList();

        return new Table { Headers = headers, Rows = rows };
    }
}
