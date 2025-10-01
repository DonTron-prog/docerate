import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import './App.css';
import Navigation from './components/Navigation';
import AIExplorer from './pages/AIExplorer';
import BlogList from './components/BlogList';
import BlogPost from './components/BlogPost';

function AppContent() {
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const selectedTag = queryParams.get('tag') || undefined;

  return (
    <div className="App">
      <Navigation />

      <main className="app-main">
        <Routes>
          <Route path="/" element={<AIExplorer />} />
          <Route path="/blog" element={<BlogList selectedTag={selectedTag} />} />
          <Route path="/blog/:slug" element={<BlogPost />} />
        </Routes>
      </main>

      <footer className="app-footer">
        <p>
          Powered by RAG (Retrieval-Augmented Generation) |
          <a href="http://localhost:5000/docs" target="_blank" rel="noopener noreferrer"> API Docs</a> |
          <a href="https://github.com/DonTron-prog/dontron_blog" target="_blank" rel="noopener noreferrer"> GitHub</a>
        </p>
      </footer>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;