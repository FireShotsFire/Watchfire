"use client";

import React, { useState } from "react";
import { Search, ShieldAlert, CheckCircle2, ExternalLink, FileText, AlertTriangle } from "lucide-react";

interface MatchResult {
  match_score: number;
  official_id: string;
  jurisdiction: string;
  entity_type: string;
  primary_name: string;
  matched_alias: string | null;
  dates_of_birth: string[];
  regime_reasons: string;
  official_source_url: string;
}

export default function WatchfireDashboard() {
  const [queryName, setQueryName] = useState("");
  const [threshold, setThreshold] = useState(65);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [searched, setSearched] = useState(false);
  
  // Decision state per hit ID
  const [decisions, setDecisions] = useState<{ [key: string]: { status: string; notes: string } }>({});

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://watchfire-s42r.onrender.com";

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryName.trim()) return;

    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/screen?name=${encodeURIComponent(queryName)}&threshold=${threshold}`
      );
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Screening request failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDecisionChange = (id: string, status: string) => {
    setDecisions((prev) => ({
      ...prev,
      [id]: { status, notes: prev[id]?.notes || "" },
    }));
  };

  const handleNotesChange = (id: string, notes: string) => {
    setDecisions((prev) => ({
      ...prev,
      [id]: { status: prev[id]?.status || "PENDING", notes },
    }));
  };

  const exportAuditLog = (item: MatchResult) => {
    const decision = decisions[item.official_id] || { status: "UNREVIEWED", notes: "None provided" };
    const logData = `=====================================================
WATCHFIRE SANCTIONS SCREENING AUDIT RECORD
=====================================================
Timestamp: ${new Date().toISOString()}
Search Query Subject: ${queryName}
Screening Sensitivity Threshold: ${threshold}%

MATCH DETAILS:
-----------------------------------------------------
Primary Name: ${item.primary_name}
Jurisdiction: ${item.jurisdiction}
Official ID: ${item.official_id}
Entity Type: ${item.entity_type}
Match Score: ${item.match_score}%
Official Source: ${item.official_source_url}

COMPLIANCE REVIEWER DECISION:
-----------------------------------------------------
Review Outcome: ${decision.status}
Reviewer Notes: ${decision.notes}
=====================================================`;

    const blob = new Blob([logData], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `watchfire_audit_${item.official_id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <header className="border-b border-slate-800 pb-6 mb-8 flex justify-between items-center">
        <div>
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-8 h-8 text-amber-500" />
            <h1 className="text-2xl font-bold tracking-tight text-white">WATCHFIRE</h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Multi-Jurisdictional Sanctions Aggregator & Compliance Review Console
          </p>
        </div>
        <span className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-full text-xs font-mono text-slate-300">
          UK • US • EU Lists Active
        </span>
      </header>

      {/* Search Bar Workspace */}
      <section className="bg-slate-800/60 border border-slate-700/80 rounded-lg p-6 mb-8 shadow-lg">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-3.5 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Enter person or company name to screen..."
                value={queryName}
                onChange={(e) => setQueryName(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-slate-900 border border-slate-700 rounded-md text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500 font-medium"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-3 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 text-white font-semibold rounded-md transition-colors flex items-center justify-center gap-2"
            >
              {loading ? "Screening..." : "Screen Subject"}
            </button>
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-400 pt-2">
            <span>Match Sensitivity Threshold: <strong className="text-amber-400">{threshold}%</strong></span>
            <input
              type="range"
              min="40"
              max="95"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-48 accent-amber-500 cursor-pointer"
            />
          </div>
        </form>
      </section>

      {/* Results Workspace */}
      {searched && (
        <section className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-slate-200">
              Screening Results for <span className="text-amber-400">"{queryName}"</span>
            </h2>
            <span className="text-xs text-slate-400">
              Found {results.length} candidate hit(s)
            </span>
          </div>

          {results.length === 0 ? (
            <div className="bg-slate-800/40 border border-slate-800 rounded-lg p-8 text-center">
              <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
              <h3 className="text-slate-200 font-medium">No Matches Detected</h3>
              <p className="text-slate-400 text-sm mt-1">
                No entities on UK or US lists exceeded the {threshold}% sensitivity threshold.
              </p>
            </div>
          ) : (
            results.map((hit) => {
              const currentDecision = decisions[hit.official_id] || { status: "PENDING", notes: "" };

              return (
                <div
                  key={`${hit.jurisdiction}-${hit.official_id}`}
                  className="bg-slate-800/80 border border-slate-700 rounded-lg p-6 space-y-4"
                >
                  {/* Top Bar Matrix */}
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b border-slate-700 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono rounded">
                          {hit.jurisdiction} SANCTION
                        </span>
                        <span className="text-xs text-slate-400 font-mono">ID: {hit.official_id}</span>
                      </div>
                      <h3 className="text-xl font-bold text-white mt-1">{hit.primary_name}</h3>
                      {hit.matched_alias && (
                        <span className="text-xs text-amber-300 italic">{hit.matched_alias}</span>
                      )}
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-xs text-slate-400">Match Confidence</div>
                        <div className="text-2xl font-black text-amber-400 font-mono">{hit.match_score}%</div>
                      </div>
                    </div>
                  </div>

                  {/* Side-by-Side Comparison Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm bg-slate-900/60 p-4 rounded border border-slate-800">
                    <div>
                      <span className="text-xs uppercase font-semibold text-slate-500 block mb-1">Target Subject</span>
                      <p className="text-slate-200 font-medium">{queryName}</p>
                    </div>
                    <div>
                      <span className="text-xs uppercase font-semibold text-slate-500 block mb-1">Sanctioned Entity Match</span>
                      <p className="text-slate-200 font-medium">{hit.primary_name}</p>
                      <p className="text-slate-400 text-xs mt-1">
                        <strong>Regime Basis:</strong> {hit.regime_reasons || "N/A"}
                      </p>
                    </div>
                  </div>

                  {/* Official Source Lineage Link */}
                  <div className="flex items-center justify-between pt-1">
                    <a
                      href={hit.official_source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-amber-400 hover:underline flex items-center gap-1"
                    >
                      Verify Official Source Record <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>

                  {/* Human-in-the-Loop Compliance Review Panel */}
                  <div className="border-t border-slate-700/80 pt-4 mt-2 space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      HUMAN REVIEWER DECISION PANEL
                    </div>

                    <div className="flex flex-col md:flex-row gap-3">
                      <select
                        value={currentDecision.status}
                        onChange={(e) => handleDecisionChange(hit.official_id, e.target.value)}
                        className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-amber-500"
                      >
                        <option value="PENDING">Status: Pending Review</option>
                        <option value="FALSE_POSITIVE">Status: Confirmed False Positive</option>
                        <option value="CONFIRMED_MATCH">Status: Confirmed Sanctions Match</option>
                        <option value="ESCALATED">Status: Escalated to MLRO</option>
                      </select>

                      <input
                        type="text"
                        placeholder="Add mandatory review justification notes..."
                        value={currentDecision.notes}
                        onChange={(e) => handleNotesChange(hit.official_id, e.target.value)}
                        className="flex-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-amber-500"
                      />

                      <button
                        onClick={() => exportAuditLog(hit)}
                        className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-xs text-white rounded font-medium flex items-center justify-center gap-1.5 transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        Export Audit Record
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </section>
      )}
    </div>
  );
}
