import React from 'react';
import { NavLink } from 'react-router-dom';
import './Navigation.css';

const Navigation: React.FC = () => {
  return (
    <nav className="main-navigation">
      <div className="nav-container">
        <div className="nav-brand">
          <h1>Donald McGillivray</h1>
        </div>

        <div className="nav-tabs">
          <NavLink
            to="/"
            className={({ isActive }) =>
              isActive ? 'nav-tab active' : 'nav-tab'
            }
            end
          >
            AI Explorer
          </NavLink>

          <NavLink
            to="/blog"
            className={({ isActive }) =>
              isActive ? 'nav-tab active' : 'nav-tab'
            }
          >
            Blog Posts
          </NavLink>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;