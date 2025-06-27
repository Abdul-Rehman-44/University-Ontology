#!/usr/bin/env python3
"""
Knowledge Representation and Reasoning (KRR) System
A sophisticated Flask-based application for ontology management and semantic reasoning.

Author: KRR Development Team
Version: 1.0.0
License: MIT
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Flask, render_template, request, jsonify, abort, make_response
from flask_cors import CORS
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery
import requests
from werkzeug.exceptions import HTTPException
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('krr_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Enable CORS for development
CORS(app)

# Global variables
ontology_graph = None
university_ns = None

class OntologyManager:
    """Manages ontology operations and SPARQL queries."""
    
    def __init__(self, ontology_file: str = 'university.owl'):
        self.ontology_file = ontology_file
        self.graph = Graph()
        self.namespace = None
        self.load_ontology()
    
    def load_ontology(self):
        """Load the OWL ontology file."""
        try:
            if os.path.exists(self.ontology_file):
                self.graph.parse(self.ontology_file, format='xml')
                logger.info(f"Successfully loaded ontology from {self.ontology_file}")
                
                # Define namespace
                self.namespace = Namespace("http://www.semanticweb.org/university#")
                self.graph.bind('university', self.namespace)
            else:
                logger.warning(f"Ontology file {self.ontology_file} not found. Creating sample ontology.")
                self.create_sample_ontology()
        except Exception as e:
            logger.error(f"Error loading ontology: {str(e)}")
            self.create_sample_ontology()
    
    def create_sample_ontology(self):
        """Create a sample university ontology if the file doesn't exist."""
        try:
            # Define namespace
            self.namespace = Namespace("http://www.semanticweb.org/university#")
            self.graph.bind('university', self.namespace)
            
            # Add classes
            self.graph.add((self.namespace.University, RDF.type, OWL.Class))
            self.graph.add((self.namespace.Student, RDF.type, OWL.Class))
            self.graph.add((self.namespace.Professor, RDF.type, OWL.Class))
            self.graph.add((self.namespace.Course, RDF.type, OWL.Class))
            self.graph.add((self.namespace.Department, RDF.type, OWL.Class))
            
            # Add properties
            self.graph.add((self.namespace.enrolledIn, RDF.type, OWL.ObjectProperty))
            self.graph.add((self.namespace.teaches, RDF.type, OWL.ObjectProperty))
            self.graph.add((self.namespace.belongsTo, RDF.type, OWL.ObjectProperty))
            self.graph.add((self.namespace.hasName, RDF.type, OWL.DatatypeProperty))
            self.graph.add((self.namespace.hasEmail, RDF.type, OWL.DatatypeProperty))
            
            # Add individuals
            self.graph.add((self.namespace.JohnDoe, RDF.type, self.namespace.Student))
            self.graph.add((self.namespace.JohnDoe, self.namespace.hasName, Literal("John Doe")))
            self.graph.add((self.namespace.JohnDoe, self.namespace.hasEmail, Literal("john.doe@university.edu")))
            
            self.graph.add((self.namespace.DrSmith, RDF.type, self.namespace.Professor))
            self.graph.add((self.namespace.DrSmith, self.namespace.hasName, Literal("Dr. Jane Smith")))
            self.graph.add((self.namespace.DrSmith, self.namespace.hasEmail, Literal("jane.smith@university.edu")))
            
            self.graph.add((self.namespace.CS101, RDF.type, self.namespace.Course))
            self.graph.add((self.namespace.CS101, self.namespace.hasName, Literal("Introduction to Computer Science")))
            
            # Add relationships
            self.graph.add((self.namespace.JohnDoe, self.namespace.enrolledIn, self.namespace.CS101))
            self.graph.add((self.namespace.DrSmith, self.namespace.teaches, self.namespace.CS101))
            
            logger.info("Sample ontology created successfully")
        except Exception as e:
            logger.error(f"Error creating sample ontology: {str(e)}")
    
    def execute_sparql_query(self, query: str) -> List[Dict]:
        """Execute a SPARQL query and return results."""
        try:
            prepared_query = prepareQuery(query)
            results = self.graph.query(prepared_query)
            
            # Convert results to list of dictionaries
            result_list = []
            for row in results:
                row_dict = {}
                for var in results.vars:
                    value = row[var]
                    if value:
                        if hasattr(value, 'toPython'):
                            row_dict[str(var)] = value.toPython()
                        else:
                            row_dict[str(var)] = str(value)
                result_list.append(row_dict)
            
            return result_list
        except Exception as e:
            logger.error(f"Error executing SPARQL query: {str(e)}")
            return []
    
    def get_all_classes(self) -> List[str]:
        """Get all classes from the ontology."""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?class
        WHERE {
            ?class rdf:type owl:Class .
        }
        """
        results = self.execute_sparql_query(query)
        return [result['class'].split('#')[-1] for result in results if 'class' in result]
    
    def get_all_individuals(self) -> List[Dict]:
        """Get all individuals from the ontology."""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX university: <http://www.semanticweb.org/university#>
        SELECT DISTINCT ?individual ?type ?name ?email
        WHERE {
            ?individual rdf:type ?type .
            OPTIONAL { ?individual university:hasName ?name . }
            OPTIONAL { ?individual university:hasEmail ?email . }
            FILTER(?type != <http://www.w3.org/2002/07/owl#Class>)
        }
        """
        return self.execute_sparql_query(query)

# Initialize ontology manager
ontology_manager = OntologyManager()

@app.route('/')
def index():
    """Main application page."""
    return render_template('index.html')

@app.route('/api/ontology/classes', methods=['GET'])
def get_classes():
    """API endpoint to get all ontology classes."""
    try:
        classes = ontology_manager.get_all_classes()
        return jsonify({
            'success': True,
            'data': classes,
            'count': len(classes),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting classes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/ontology/individuals', methods=['GET'])
def get_individuals():
    """API endpoint to get all ontology individuals."""
    try:
        individuals = ontology_manager.get_all_individuals()
        return jsonify({
            'success': True,
            'data': individuals,
            'count': len(individuals),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting individuals: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/ontology/query', methods=['POST'])
def execute_query():
    """API endpoint to execute custom SPARQL queries."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query parameter is required',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        query = data['query']
        results = ontology_manager.execute_sparql_query(query)
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'query': query,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/ontology/stats', methods=['GET'])
def get_ontology_stats():
    """API endpoint to get ontology statistics."""
    try:
        # Get basic statistics
        total_triples = len(ontology_manager.graph)
        classes = ontology_manager.get_all_classes()
        individuals = ontology_manager.get_all_individuals()
        
        stats = {
            'total_triples': total_triples,
            'total_classes': len(classes),
            'total_individuals': len(individuals),
            'classes': classes,
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting ontology stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'KRR System',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'ontology_loaded': ontology_manager.graph is not None
    })

@app.route('/final-report')
def final_report():
    return render_template('final_report.html')

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'success': False,
        'error': 'Resource not found',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({
        'success': False,
        'error': 'An unexpected error occurred',
        'timestamp': datetime.now().isoformat()
    }), 500

if __name__ == '__main__':
    # Development server configuration
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
