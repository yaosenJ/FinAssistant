### 目录说明
1. **qa_pairs**(第一版生成的评估数据目录) 
   - `rag_results_2776_v1.csv`: 使用**text-embedding-v1**向量化的评估召回率的生成结果数据
   - `rag_results_2776_v3.csv`: 使用**text-embedding-v3**向量化的评估召回率的生成结果数据
   - `rag_results_2776_v3_re.csv`: 增加重排模型(gte-rerank-v2)，使用**text-embedding-v3**向量化的评估召回率的生成结果数据
   - `rag_results_hybrid.csv`: 增加混合检索，使用**text-embedding-v3**向量化的评估召回率的生成结果数据
2. **qa_pairs_update** (第二版生成的评估数据目录，必须包含主体的新闻)  
   - `rag_results_2776_v3_re_bge-reranker-large.csv`: 增加本地部署的重排模型(bge-reranker-large)，使用**text-embedding-v3**向量化的评估召回率的生成结果数据
   - `rag_results_hybrid.csv`: 增加混合检索，使用**text-embedding-v3**向量化的评估召回率的生成结果数据
3. **qa_pairs.csv**  
   - 第一版生成的评估数据
4. **qa_pairs.csv**  
   - 第二版生成的评估数据
5. **time.csv**
   - 个股交易日期


