import React from 'react';
import Layout from '../components/Layout';
import { FileText, Lightbulb, BookOpen, Play, Star, CheckSquare } from 'lucide-react';

const AITools: React.FC = () => {
  return (
    <Layout userEmail="user@example.com" userInitials="U">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">AI Tools</h1>
        <p className="text-slate-600 mb-6">
          AI-powered research analysis tools • 2 papers available • 2 selected
        </p>

        {/* Select Papers Section */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Select Papers for Analysis</h2>
          <div className="space-y-3">
            <label className="flex items-start gap-3 p-3 rounded-lg border border-red-200 bg-red-50 cursor-pointer">
              <input type="checkbox" checked className="mt-1 h-4 w-4 rounded border-red-300 text-red-600" />
              <div className="flex-1">
                <p className="font-medium text-slate-900">AI Agents and Agentic AI - Navigating a Plethora of Concepts for Future Manufacturing</p>
                <p className="text-sm text-slate-600 mt-1">Tinwang Ren, Yangyang Liu, Yang Si, Xun Xu</p>
              </div>
            </label>
            <label className="flex items-start gap-3 p-3 rounded-lg border border-red-200 bg-red-50 cursor-pointer">
              <input type="checkbox" checked className="mt-1 h-4 w-4 rounded border-red-300 text-red-600" />
              <div className="flex-1">
                <p className="font-medium text-slate-900">Responsible AI Agents</p>
                <p className="text-sm text-slate-600 mt-1">Demis R. Hassabis, David Silver, Marc G. Raibert</p>
              </div>
            </label>
          </div>
          <p className="mt-4 text-sm text-slate-600">2 paper(s) selected</p>
        </div>

        {/* Three Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* AI Summaries - Blue */}
          <div className="bg-white rounded-lg border border-blue-200 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileText className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">AI Summaries</h3>
                <p className="text-sm text-slate-600">Generate concise summaries of selected research papers</p>
              </div>
            </div>
            <button className="w-full bg-blue-600 text-white px-4 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors flex items-center justify-center gap-2">
              <Play className="h-4 w-4" />
              Generate Summaries
            </button>
          </div>

          {/* Key Insights - Orange */}
          <div className="bg-white rounded-lg border border-orange-200 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-orange-100 rounded-lg">
                <Lightbulb className="h-6 w-6 text-orange-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Key Insights</h3>
                <p className="text-sm text-slate-600">Extract key insights and trends from research papers</p>
              </div>
            </div>
            <button className="w-full bg-orange-600 text-white px-4 py-3 rounded-lg font-semibold hover:bg-orange-700 transition-colors flex items-center justify-center gap-2">
              <Star className="h-4 w-4" />
              Extract Insights
            </button>
          </div>

          {/* Literature Review - Green */}
          <div className="bg-white rounded-lg border border-green-200 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <BookOpen className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Literature Review</h3>
                <p className="text-sm text-slate-600">Generate comprehensive literature reviews automatically</p>
              </div>
            </div>
            <button className="w-full bg-green-600 text-white px-4 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors flex items-center justify-center gap-2">
              <CheckSquare className="h-4 w-4" />
              Generate Review
            </button>
          </div>
        </div>

        {/* Results Sections */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-slate-900">AI Summaries Results</h2>
            <button className="text-slate-600 hover:text-slate-900 text-sm font-medium">Download</button>
          </div>
          <div className="space-y-4 text-sm text-slate-700">
            <div>
              <h3 className="font-semibold mb-2">AI Agents and Agentic AI - Navigating a Plethora of Concepts for Future Manufacturing</h3>
              <p className="text-slate-600">
                This paper explores the evolution of AI and AI agent technologies, focusing on LLM-Agents, MLLM-Agents, and Agentic AI...
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Responsible AI Agents</h3>
              <p className="text-slate-600">
                This paper addresses concerns around potential risks and harms of AI Agents, proposing a computer-science approach...
              </p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default AITools;

