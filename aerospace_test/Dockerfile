FROM ubuntu

COPY . ./

RUN apt-get update && \
    apt-get install -y build-essential  && \
    apt-get install -y wget

ENV CONDA_DIR /opt/conda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
     /bin/bash ~/miniconda.sh -b -p /opt/conda

ENV PATH=$CONDA_DIR/bin:$PATH

RUN conda config --add channels https://conda.anaconda.org/conda-forge/

RUN conda install --file requirements.txt

EXPOSE 8000

CMD ["uvicorn", "--app-dir=app" ,"main:app", "--host", "0.0.0.0", "--port", "8000"]