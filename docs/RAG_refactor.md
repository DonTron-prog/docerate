RAG-Powered Website Implementation Plan                                                                                                  
                                                                                                                                          
 Based on your requirements and existing infrastructure, here's a comprehensive plan to transform your static blog into a RAG-powered dynamic content generation website:
                                                                                                                                          
 Architecture Overview                                                                                                                    
                                                                                                                                          
 Frontend (React App):                                                                                                                    
 - Landing page with interactive tag cloud                                                                                                
 - Topic selection interface with tag filtering                                                                                           
 - Optional context/question input textbox                                                                                               
 - Generated article display with references                                                                                              
 - Deployed to S3/CloudFront                                                                                                              
                                                                                                                                          
 Backend (AWS Lambda Functions):                                                                                                          
 - Indexing Lambda: Process markdown posts, chunk by sections, generate embeddings                                                        
 - Search Lambda: Handle hybrid search (semantic + keyword), return relevant chunks                                                       
 - Generation Lambda: Generate custom articles using Bedrock models                                                                       
 - API Gateway: RESTful endpoints for frontend-backend communication                                                                      
                                                                                                                                          
 Storage & Processing:                                                                                                                    
 - S3: Store preprocessed chunks, embeddings, and BM25 indexes as JSON                                                                    
 - DynamoDB (optional): Store metadata and user sessions                                                                                  
 - CloudFront: CDN for both static site and API caching                                                                                   
                                                                                                                                          
 Implementation Steps                                                                                                                     
                                                                                                                                          
 Phase 1: Data Processing & Indexing                                                                                                      
                                                                                                                                          
 1. Create indexing pipeline script (rag_indexer.py)                                                                                      
   - Parse existing markdown posts (H2/H3 sections)                                                                                       
   - Generate semantic chunks preserving boundaries                                                                                       
   - Extract metadata (title, tags, date, URLs with fragments)                                                                            
   - Generate embeddings using Bedrock Titan Embeddings                                                                                   
   - Calculate BM25 statistics for keyword search                                                                                         
   - Export as JSON artifacts to S3                                                                                                       
 2. Update CI/CD pipeline (.github/workflows/deploy.yml)                                                                                  
   - Add indexing step after build                                                                                                        
   - Upload RAG artifacts to S3 bucket                                                                                                    
                                                                                                                                          
 Phase 2: Backend Services                                                                                                                
                                                                                                                                          
 3. Create Lambda functions:                                                                                                              
   - rag-search-lambda: Hybrid search implementation                                                                                      
       - Load embeddings from S3 (cached in memory)                                                                                       
     - Perform vector similarity search                                                                                                   
     - Apply BM25 keyword matching                                                                                                        
     - Use RRF for result fusion                                                                                                          
     - Return top-k chunks with metadata                                                                                                  
   - rag-generate-lambda: Content generation                                                                                              
       - Receive user query and selected tags                                                                                             
     - Call search Lambda for relevant chunks                                                                                             
     - Construct prompt with retrieved context                                                                                            
     - Call Bedrock Claude/Llama for generation                                                                                           
     - Format response with references                                                                                                    
     - Preserve your writing style through prompt engineering                                                                             
 4. Configure API Gateway                                                                                                                 
   - /api/search - POST endpoint for chunk retrieval                                                                                      
   - /api/generate - POST endpoint for article generation                                                                                 
   - /api/tags - GET endpoint for available tags                                                                                          
   - Enable CORS for frontend access                                                                                                      
                                                                                                                                          
 Phase 3: Frontend Development                                                                                                            
                                                                                                                                          
 5. Create React application (rag-frontend/)                                                                                              
   - Component structure:                                                                                                                 
       - TagCloud.jsx - Interactive tag visualization                                                                                     
     - QueryInput.jsx - User input interface                                                                                              
     - ArticleDisplay.jsx - Generated content viewer                                                                                      
     - References.jsx - Source article links                                                                                              
   - State management for user selections                                                                                                 
   - API integration with error handling                                                                                                  
 6. Implement key features:                                                                                                               
   - Visual tag cloud with D3.js or similar                                                                                               
   - Multi-select tag filtering                                                                                                           
   - Real-time search preview                                                                                                             
   - Markdown rendering for generated content                                                                                             
   - Citation links to original articles                                                                                                  
                                                                                                                                          
 Phase 4: Infrastructure & Deployment                                                                                                     
                                                                                                                                          
 7. AWS Configuration:                                                                                                                    
   - IAM roles for Lambda execution                                                                                                       
   - S3 buckets for artifacts and frontend                                                                                                
   - CloudFront distributions                                                                                                             
   - Route 53 DNS configuration                                                                                                           
   - API Gateway custom domain                                                                                                            
 8. Monitoring & Optimization:                                                                                                            
   - CloudWatch metrics for Lambda performance                                                                                            
   - X-Ray tracing for latency analysis                                                                                                   
   - Cost optimization through caching                                                                                                    
   - A/B testing for retrieval strategies                                                                                                 
                                                                                                                                          
 Technical Specifications                                                                                                                 
                                                                                                                                          
 Chunking Strategy:                                                                                                                       
 - Primary: Semantic sections (H2/H3 boundaries)                                                                                          
 - Token limit: 512 tokens per chunk                                                                                                      
 - Overlap: 50 tokens between adjacent chunks                                                                                             
 - Metadata: post_slug, section_id, heading, position, tags                                                                               
                                                                                                                                          
 Retrieval Configuration:                                                                                                                 
 - Embedding model: Amazon Titan Text Embeddings V2                                                                                       
 - Vector similarity: Cosine similarity                                                                                                   
 - Initial retrieval: Top-20 candidates                                                                                                   
 - Reranking: Top-5 final chunks                                                                                                          
 - Hybrid weight: 0.7 semantic, 0.3 keyword                                                                                               
                                                                                                                                          
 Generation Prompt Template:                                                                                                              
 You are Donald McGillivray, author of technical blog posts. Generate an article based on the user's query using the provided context chunks. Maintain the technical depth and writing style from the source material.
                                                                                                                                          
 Context chunks:                                                                                                                          
 {retrieved_chunks}                                                                                                                       
                                                                                                                                          
 User query: {user_query}                                                                                                                 
 Selected topics: {selected_tags}                                                                                                         
                                                                                                                                          
 Generate a cohesive article that:                                                                                                        
 1. Addresses the user's specific question                                                                                                
 2. Maintains technical accuracy                                                                                                          
 3. Uses your characteristic writing style                                                                                                
 4. Includes [ref:N] citations for source chunks                                                                                          
                                                                                                                                          
 File Structure                                                                                                                           
                                                                                                                                          
 dontron_blog/                                                                                                                            
 ├── rag/                                                                                                                                 
 │   ├── indexer.py          # Offline processing                                                                                         
 │   ├── embeddings.py        # Bedrock integration                                                                                       
 │   ├── chunker.py           # Document chunking                                                                                         
 │   └── bm25.py              # Keyword search                                                                                            
 ├── lambda/                                                                                                                              
 │   ├── search/              # Search Lambda                                                                                             
 │   ├── generate/            # Generation Lambda                                                                                         
 │   └── requirements.txt                                                                                                                 
 ├── rag-frontend/            # React app                                                                                                 
 │   ├── src/                                                                                                                             
 │   ├── public/                                                                                                                          
 │   └── package.json                                                                                                                     
 └── infrastructure/                                                                                                                      
     ├── terraform/           # IaC (optional)                                                                                            
     └── cloudformation/      # Alternative IaC                                                                                           
                                                                                                                                          
 Estimated Timeline                                                                                                                       
                                                                                                                                          
 - Week 1-2: Data processing pipeline & indexing                                                                                          
 - Week 2-3: Lambda functions & API Gateway                                                                                               
 - Week 3-4: React frontend development                                                                                                   
 - Week 4-5: Integration, testing & optimization                                                                                          
 - Week 5-6: Deployment & monitoring setup                                                                                                
                                                                                                                                          
 This plan provides a scalable foundation that can start with in-memory search (<50MB vectors) and later migrate to a vector database as your content grows.