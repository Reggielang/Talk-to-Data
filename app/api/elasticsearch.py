"""Elasticsearch 索引管理 API 路由."""

import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.api.schemas import (
    ESIndexCreateRequest,
    ESDocumentCreateRequest,
    ESIndexResponse,
    ESIndexInfoResponse,
    ErrorResponse,
)
from app.services.elasticsearch_service import elasticsearch_service


router = APIRouter(
    prefix="/es",
    tags=["elasticsearch"],
)


# ==================== 索引管理 ====================

@router.post(
    "/index/create",
    response_model=ESIndexResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def create_index(request: ESIndexCreateRequest):
    """创建 Elasticsearch 索引."""
    try:
        result = elasticsearch_service.create_index(request.index_name)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "创建索引失败"),
            )

        logger.info(f"[ESAPI] Index created: {request.index_name}")
        return ESIndexResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ESAPI] Create index error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建索引失败: {str(e)}",
        )


@router.delete(
    "/index/{index_name}",
    response_model=ESIndexResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def delete_index(index_name: str):
    """删除 Elasticsearch 索引."""
    try:
        result = elasticsearch_service.delete_index(index_name)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "删除索引失败"),
            )

        logger.info(f"[ESAPI] Index deleted: {index_name}")
        return ESIndexResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ESAPI] Delete index error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除索引失败: {str(e)}",
        )


@router.get(
    "/index/{index_name}/exists",
    response_model=ESIndexInfoResponse,
    responses={500: {"model": ErrorResponse}},
)
async def check_index_exists(index_name: str):
    """检查索引是否存在."""
    try:
        result = elasticsearch_service.index_exists(index_name)
        return ESIndexInfoResponse(**result)

    except Exception as e:
        logger.error(f"[ESAPI] Check index exists error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查索引失败: {str(e)}",
        )


@router.get(
    "/index/{index_name}/info",
    response_model=ESIndexInfoResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_index_info(index_name: str):
    """获取索引详细信息."""
    try:
        result = elasticsearch_service.get_index_info(index_name)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "获取索引信息失败"),
            )

        return ESIndexInfoResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ESAPI] Get index info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取索引信息失败: {str(e)}",
        )


# ==================== 文档管理 ====================

@router.post(
    "/document/add",
    response_model=ESIndexResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def add_document(request: ESDocumentCreateRequest):
    """添加文档到索引."""
    try:
        # 自动生成 UUID（无横线）
        doc_id = request.id if request.id else uuid.uuid4().hex

        document = {
            "id": doc_id,
            "question": request.question,
            "content": request.content,
        }

        result = elasticsearch_service.add_document(request.index_name, document, request.auto_embedding)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "添加文档失败"),
            )

        logger.info(f"[ESAPI] Document added to '{request.index_name}': {doc_id}")
        return ESIndexResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ESAPI] Add document error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加文档失败: {str(e)}",
        )
