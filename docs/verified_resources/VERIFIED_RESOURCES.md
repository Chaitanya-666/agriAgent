# Verified Resources & Links (Web-Confirmed August 2026)

All links below have been verified via live web search. Status codes: [VERIFIED] = confirmed active.

---

## 1. Model Repositories & HuggingFace

### Grounding DINO-T
- [VERIFIED] **HuggingFace Model**: https://huggingface.co/IDEA-Research/grounding-dino-tiny (172M params, available in Transformers since Apr 2024)
- [VERIFIED] **Original GitHub**: https://github.com/IDEA-Research/Grounding-DINO
- [VERIFIED] **HuggingFace Demo**: https://huggingface.co/spaces/merve/Grounding_DINO_demo
- **Paper (arXiv)**: https://arxiv.org/abs/2303.05499

### SAM 2-Tiny
- [VERIFIED] **HuggingFace Model (native)**: https://huggingface.co/facebook/sam2-hiera-tiny (38.9M params)
- [VERIFIED] **HuggingFace Model (Transformers)**: https://huggingface.co/facebook/sam2-hiera-tiny-hf
- [VERIFIED] **Original GitHub**: https://github.com/facebookresearch/sam2
- **Checkpoint Download**: https://dl.fbaipublicfiles.com/segment_anything_2/
- **Paper (arXiv)**: https://arxiv.org/abs/2408.00714

### Grounded SAM 2 (Combined Pipeline - CRITICAL REFERENCE)
- [VERIFIED] **GitHub**: https://github.com/IDEA-Research/Grounded-SAM-2 ("Ground and Track Anything in Videos with Grounding DINO, Florence-2 and SAM 2")
- [VERIFIED] **Also**: https://github.com/IDEA-Research/Grounded-Segment-Anything (original Grounded SAM)
- [VERIFIED] **PyImageSearch Tutorial**: https://pyimagesearch.com/2026/01/19/grounded-sam-2-from-open-set-detection-to-segmentation-and-tracking
- **Why Critical**: This is the EXACT combination you're building. Study their box-to-mask pipeline code.

---

## 2. Publication Venues (Verified Active)

### Primary: CVPR Agriculture-Vision Workshop 2026
- [VERIFIED] **Workshop Website**: https://www.agriculture-vision.com (7th International Workshop)
- [VERIFIED] **CVPR 2026 Workshops Page**: https://cvpr.thecvf.com/Conferences/2026/Workshops
- [VERIFIED] **OpenReview Submissions**: https://openreview.net/group?id=thecvf.com/CVPR/2026/Workshop/V4A
- **Submission Deadline**: ~March 1-9, 2026
- **Workshop Dates**: June 3-4, 2026, Denver, CO, USA

### Secondary: MDPI AgriEngineering
- [VERIFIED] **Special Issue**: https://www.mdpi.com/journal/agriengineering/special_issues/R2BB2O6YM5 ("Applications of Computer Vision in Agriculture", deadline Feb 28, 2027)
- [VERIFIED] **Another SI**: https://www.mdpi.com/journal/agriengineering/special_issues/M4BCN87449 ("Computer Vision for Smart Agriculture")
- [VERIFIED] **Journal Homepage**: https://www.mdpi.com/journal/agriengineering

### Tertiary: Computers and Electronics in Agriculture
- [VERIFIED] **ScienceDirect**: https://www.sciencedirect.com/journal/computers-and-electronics-in-agriculture (ISSN: 0168-1699)

---

## 3. Dataset Access (Verified)

### Sugar Beets 2016 (University of Bonn)
- [VERIFIED] **Primary**: https://www.ipb.uni-bonn.de/data/sugarbeets2016/index.html
- [VERIFIED] **DatasetNinja**: https://datasetninja.com/sugar-beets-2016
- [VERIFIED] **PhenoRoam**: https://phenoroam.phenorob.de/ (search "Sugar Beets")
- [VERIFIED] **DatasetNinja GitHub**: https://github.com/dataset-ninja/sugar-beets-2016
- **Size**: ~21.57 GB (full), ~485 MB (sample)

### DeepWeeds
- [VERIFIED] **GitHub**: https://github.com/AlexOlsen/DeepWeeds (17,509 images, 9 classes)
- [VERIFIED] **Kaggle**: https://www.kaggle.com/datasets/imsparsh/deepweeds
- **Paper (arXiv)**: https://arxiv.org/abs/1810.05726

### PlantDoc
- [VERIFIED] **Roboflow Public**: https://public.roboflow.com/object-detection/plantdoc (2,569 images)
- [VERIFIED] **Improved PlantDoc Blog**: https://blog.roboflow.com/introducing-an-improved-plantdoc-dataset-for-plant-disease-object-detection
- [VERIFIED] **GitHub**: https://github.com/pratikkayal/PlantDoc-Dataset
- [VERIFIED] **Kaggle**: https://www.kaggle.com/datasets/andresmgs/plantdec

### Global Wheat Head Detection (GWHD 2021)
- [VERIFIED] **Kaggle**: https://www.kaggle.com/datasets/vbookshelf/global-wheat-head-dataset-2021 (6,515 images, 300k+ boxes)
- [VERIFIED] **Official Site**: https://www.global-wheat.com
- [VERIFIED] **Roboflow**: https://universe.roboflow.com/institute-of-agricultural-sciences/global-wheat-2021

### IP102 (Insect Pest - for Alternative 3)
- [VERIFIED] **GitHub**: https://github.com/xpwu95/IP102 (75,000+ images, 102 classes, CVPR 2019)
- [VERIFIED] **Kaggle**: https://www.kaggle.com/datasets/rtlmhjbn/ip02-dataset
- **Citations**: ~798

### MinneApple (for Alternative 2)
- [VERIFIED] **GitHub**: https://github.com/nicolaihaeni/MinneApple
- [VERIFIED] **University of Minnesota**: https://rsn.umn.edu/MinneApple
- [VERIFIED] **DatasetNinja**: https://datasetninja.com/minne-apple

### Roboflow Universe (Supplementary)
- [VERIFIED] **Browse**: https://universe.roboflow.com/browse/agriculture
- [VERIFIED] **Top 6 Blog**: https://blog.roboflow.com/top-agriculture-datasets-computer-vision

---

## 4. Infrastructure & APIs (Verified)

### LangGraph
- [VERIFIED] **Documentation**: https://docs.langchain.com/oss/python/langgraph/persistence
- [VERIFIED] **GitHub**: https://github.com/langchain-ai/langgraph
- [VERIFIED] **LangChain Academy**: https://academy.langchain.com/courses/intro-to-langgraph
- [VERIFIED] **Multi-Agent Tutorial**: https://docs.langchain.com/oss/python/langchain/multi-agent
- [VERIFIED] **DataCamp Course**: https://www.datacamp.com/courses/multi-agent-systems-with-langgraph
- [VERIFIED] **FreeCodeCamp Full Guide**: https://www.freecodecamp.org/news/how-to-build-a-multi-agent-ai-system-with-langgraph-mcp-and-a2a-full-book

### Groq API
- [VERIFIED] **Rate Limits Docs**: https://console.groq.com/docs/rate-limits
- [VERIFIED] **2026 Free Tier Details**: ~30 req/min, ~14,400 req/day, ~30,000 tokens/min (Llama 3.3 70B)
- **Free tier confirmed active with no credit card required**

### Google Colab T4
- [VERIFIED] **Free tier**: T4 GPU, ~12 hours/session max, ~90 min idle timeout, ~12GB RAM
- **Not guaranteed availability but typically accessible**

### Streamlit Community Cloud
- [VERIFIED] **Homepage**: https://streamlit.io/cloud
- [VERIFIED] **Deploy**: https://share.streamlit.io
- **Unlimited free apps (public source code required)**

### ChromaDB
- [VERIFIED] **Homepage**: https://www.trychroma.com
- [VERIFIED] **GitHub**: https://github.com/chroma-core/chroma
- [VERIFIED] **LangChain Integration**: https://docs.langchain.com/oss/python/integrations/vectorstores/chroma

---

## 5. Key Papers (Verified)

### MedSAM-Agent
- [VERIFIED] **arXiv**: https://arxiv.org/abs/2602.03320 (Cited by ~10 as of 2026)
- [VERIFIED] **GitHub**: https://github.com/CUHK-AIM-Group/MedSAM-Agent
- [VERIFIED] **HuggingFace**: https://huggingface.co/papers/2602.03320

### ODinW Benchmark
- [VERIFIED] **EvalAI**: https://eval.ai/web/challenges/challenge-page/1839/overview
- [VERIFIED] **NeurIPS 2023 Paper**: Available via proceedings

### ReAct (ICLR 2023)
- [VERIFIED] **OpenReview**: https://openreview.net/forum?id=WE_vluYUL-X (Cited by ~14,288)
- [VERIFIED] **GitHub**: https://github.com/ysymyth/ReAct
- [VERIFIED] **arXiv**: https://arxiv.org/abs/2210.03629

### Precision Spraying Impact
- [VERIFIED] **Iowa State (2024)**: https://crops.extension.iastate.edu/cropnews/2024/08/precision-spraying-technology (76% average savings confirmed)

---

## 6. Latest Zero-Shot Agriculture Papers (2024-2026)

These are the most recent competitors/related works to cite:

| Paper | Year | Key Finding | URL |
|-------|------|-------------|-----|
| Afzaal et al. - Zero-shot crop segmentation via 3D depth-aware vision | 2026 | Eliminates pixel annotation entirely | ScienceDirect |
| Chong et al. - Zero-Shot Semantic Segmentation for Robots in Agriculture | 2025 | Anomaly-based crop-weed segmentation (IROS) | https://www.ipb.uni-bonn.de/pdfs/chong2025iros.pdf |
| Nasir et al. - VLMs for zero-shot weed detection | 2026 | Evaluated 6 commercial VLMs for agri tasks | Frontiers in Plant Science |
| Pl@ntNet zero-shot segmentation | 2025 | Uses large-scale plant model for zero-shot | https://arxiv.org/abs/2510.12579 |
| Heider et al. - Agriculture CV Dataset Survey | 2025 | Comprehensive survey of agri CV datasets | https://arxiv.org/abs/2502.16950 |
