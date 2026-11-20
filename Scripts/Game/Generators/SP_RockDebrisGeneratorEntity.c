[EntityEditorProps(category: "GameScripted/Generators", description: "Rock debris generator: forest-generator style scatter of rocks, with optional terrain-normal alignment", dynamicBox: true, visible: true)]
class SP_RockDebrisGeneratorEntityClass : SCR_AreaGeneratorBaseEntityClass
{
}

//! A Forest Generator uses the following data:
//! - Levels (Top trees, Middle trees, Outlines)
//! - Clusters (Circles, Strips)
//! These are loaded, processed (data check)
//! Then trees are "generated" in a grid, managed C++ side
//! Finally, the grid is used to create entities
class SP_RockDebrisGeneratorEntity : SCR_AreaGeneratorBaseEntity
{
	/*
		Generation
	*/

	[Attribute(defvalue: "1", category: "Generation", desc: "Allow partial forest regeneration, regenerates the whole forest otherwise")]
	protected bool m_bAllowPartialRegeneration;

	[Attribute(defvalue: "0", category: "Generation", desc: "Click to regenerate the entire forest")]
	protected bool m_bRegenerateEntireForest; //!< not saved to layer (see _WB_OnKeyChanged), used as a button

	/*
		Rock Debris
	*/

	[Attribute(defvalue: "1", uiwidget: UIWidgets.Slider, category: "Rock Debris", desc: "Amount factor for rocks: 1 = as authored in the clusters, 2 = twice as many, 0 = none", params: "0 4 0.05")]
	protected float m_fRockAmount;

	[Attribute(defvalue: "1", uiwidget: UIWidgets.Slider, category: "Rock Debris", desc: "Amount factor for debris (the small pieces, prefab path containing 'Rock_Debris'): 1 = as authored, 2 = twice as many, 0 = none", params: "0 4 0.05")]
	protected float m_fDebrisAmount;

	[Attribute(defvalue: "1", uiwidget: UIWidgets.Slider, category: "Rock Debris", desc: "Terrain normal factor: 0 = upright, 1 = fully aligned to the terrain normal", params: "0 1 0.01")]
	protected float m_fTerrainNormalFactor;

	[Attribute(defvalue: "1", uiwidget: UIWidgets.Slider, category: "Rock Debris", desc: "Sink-in factor: how deep rocks are buried in the ground (scales with rock size and slope). 0 = sitting on top, 1 = natural, 3 = deeply embedded", params: "0 3 0.05")]
	protected float m_fSinkFactor;

	[Attribute(defvalue: "1", uiwidget: UIWidgets.Slider, category: "Rock Debris", desc: "Erosion factor: more rocks, and more of the big clusters, on gentle ground at the foot of steeper slopes. 0 = off. Other areas keep a base amount of rocks", params: "0 2 0.05")]
	protected float m_fErosionFactor;

	[Attribute(defvalue: "0", category: "Debug", desc: "Print how many cluster objects the slope rules rejected")]
	protected bool m_bPrintTerrainStats;

	// internal tuning (not exposed)
	protected static const string DEBRIS_KEYWORD = "Rock_Debris";
	protected static const float ROCK_BASE_SIZE = 0.9;				//!< real size [m] of a rock at scale 1
	protected static const float DEBRIS_BASE_SIZE = 0.1;			//!< real size [m] of a debris piece at scale 1
	protected static const float LIMIT_SMALL_SIZE = 0.1;			//!< [m] real size at/below which LIMIT_SMALL_ANGLE applies
	protected static const float LIMIT_LARGE_SIZE = 2;				//!< [m] real size at/above which LIMIT_LARGE_ANGLE applies
	protected static const float LIMIT_SMALL_ANGLE = 60;			//!< max slope [deg] for the smallest debris
	protected static const float LIMIT_LARGE_ANGLE = 40;			//!< max slope [deg] for the biggest boulders
	protected static const float LIMIT_SOFTNESS = 10;				//!< [deg] probability fades out over this range below the limit
	protected static const float SLOPE_DENSITY_FULL_UNTIL = 20;		//!< [deg] full density up to this slope
	protected static const float SLOPE_DENSITY_STEEP_AT = 50;		//!< [deg] slope where density reaches its minimum
	protected static const float SLOPE_DENSITY_MIN = 0.5;			//!< density on steep slopes (never removes rocks completely)
	protected static const float ZONE_NOISE_SIZE = 30;				//!< [m] size of the loose accumulation zones
	protected static const float ZONE_NOISE_FLOOR = 0.4;			//!< cluster acceptance outside accumulation zones
	protected static const int ZONE_ATTEMPTS = 12;					//!< cluster centres tried before falling back to a random one
	protected static const float EROSION_RUNOUT = 22;				//!< [m] how far uphill a steeper slope still feeds a spot
	protected static const float EROSION_MIN_DELTA = 8;				//!< [deg] slope difference where erosion starts
	protected static const float EROSION_FULL_DELTA = 25;			//!< [deg] slope difference for the full effect
	protected static const float EROSION_FLOOR_PER_FACTOR = 0.65;	//!< how much cluster acceptance drops away from slope toes, per 1.0 of erosion factor
	protected static const float EROSION_COUNT_BOOST = 1;			//!< extra object count at a perfect slope toe, per 1.0 of erosion factor
	protected static const float CONTOUR_SHARE = 0.6;				//!< share of rocks whose yaw follows the contour
	protected static const float CONTOUR_SPREAD = 25;				//!< [deg] yaw spread around the contour
	protected static const float CONTOUR_MIN_SLOPE = 4;				//!< [deg] flatter ground keeps random yaw
	protected static const float BURIAL_BASE = 0.04;				//!< [m] per 1.0 of scale on flat ground
	protected static const float BURIAL_SLOPE = 0.12;				//!< [m] extra per 1.0 of scale on a vertical slope
	protected static const int NOISE_SEED = 1;

	/*
		Debug
	*/

	[Attribute(defvalue: "0", category: "Debug", desc: "Print the area of the forest generator polygon")]
	protected bool m_bPrintArea;

	[Attribute(defvalue: "0", category: "Debug", desc: "Print the count of entities spawned by this forest generator")]
	protected bool m_bPrintEntitiesCount;

	[Attribute(defvalue: "0", category: "Debug", desc: "Print advanced performance measurements")]
	protected bool m_bPrintPerformanceDetails;

	[Attribute(defvalue: "0", category: "Debug", desc: "Draw general debug shapes")]
	protected bool m_bDrawDebugShapes;

	[Attribute(defvalue: "0", category: "Debug", desc: "Draw obstacles debug shapes")]
	protected bool m_bDrawDebugShapesObstacles;

	[Attribute(defvalue: "0", category: "Debug", desc: "Draw rectangulation debug shapes")]
	protected bool m_bDrawDebugShapesRectangulation;

	[Attribute(defvalue: "0", category: "Debug", desc: "Draw partial regeneration debug shapes")]
	protected bool m_bDrawDebugShapesRegeneration;

	[Attribute(defvalue: "1", category: "Debug", desc: "Make entities follow terrain level on shape move (keeping their relative Y)")]
	protected bool m_bEntitiesFollowTerrainOnShapeMove;

	/*
		Forest
	*/

	[Attribute(defvalue: "", category: "Forest", desc: "Forest generator levels to spawn in this forest generator polygon")]
	protected ref array<ref ForestGeneratorLevel> m_aLevels;

	[Attribute(defvalue: "", category: "Forest", desc: "Forest generator clusters to spawn in this forest generator polygon", params: "noDetails")]
	protected ref array<ref ForestGeneratorCluster> m_aClusters;

	[Attribute(defvalue: "", category: "Forest", desc: "Curve defining general outline scaling; from inside (left, forest core) to outside (right, forest outline)", uiwidget: UIWidgets.CurveDialog, params: string.Format("%1 %2 0 %3", SCALE_CURVE_RANGE, SCALE_CURVE_MAX_VALUE - SCALE_CURVE_MIN_VALUE, SCALE_CURVE_MIN_VALUE))]
	protected ref Curve m_aGlobalOutlineScaleCurve;

	[Attribute(defvalue: "0", category: "Forest", desc: "Distance from shape over which the scaling occurs", uiwidget: UIWidgets.Slider, params: "0 100 0.1")]
	protected float m_fGlobalOutlineScaleCurveDistance;

	protected static const float SCALE_CURVE_RANGE = 100; //!< distance from shape in metre
	protected static const float SCALE_CURVE_MAX_VALUE = 1;
	protected static const float SCALE_CURVE_MIN_VALUE = 0;

#ifdef WORKBENCH

	protected ref ForestGeneratorGrid m_Grid;
	protected ref array<vector> m_aShapePoints; // used by Level scale curves

	protected ref array<ref SCR_ForestGeneratorLine> m_aLines = {};
	protected ref array<ref SCR_ForestGeneratorPoint> m_aMiddleOutlinePoints = {};
	protected ref array<ref SCR_ForestGeneratorLine> m_aSmallOutlineLines = {};
	protected ref array<ref SCR_ForestGeneratorPoint> m_aSmallOutlinePoints = {};
	protected ref array<ref SCR_ForestGeneratorLine> m_aMiddleOutlineLines = {};
	protected ref array<ref SCR_ForestGeneratorRectangle> m_aRectangles = {};
	protected ref array<ref SCR_ForestGeneratorRectangle> m_aOutlineRectangles = {};
	protected ref array<ref SCR_ForestGeneratorRectangle> m_aNonOutlineRectangles = {};
	protected int m_iStatsTested;
	protected int m_iStatsRejectedPhysical;
	protected int m_iStatsRejectedProbability;
	protected float m_fClusterBoost = 1; //!< object count multiplier of the cluster currently being filled
	protected ref array<ref ForestGeneratorTreeBase> m_aGridEntries = {}; // only used to keep references for the grid, unused otherwise

	protected ref array<ref ForestGeneratorOutline> m_aOutlines = {};
	protected float m_fMaxOutlinesWidth;
	protected float m_fArea;

	protected ref map<IEntitySource, float> m_mEntitySourceATLHeights;

	protected static ref array<float> s_aPreviousPoints2D;
	protected static ref SCR_TimeMeasurementHelper s_Benchmark;

	protected static const int MAX_CLUSTER_ATTEMPT = 10;

	// debug shapes info
	protected static ref SCR_DebugShapeManager s_DebugShapeManager; // static to only have one debugged forest at a time

	protected static const int REGENERATION_DELETION_COLOUR = Color.RED;
	protected static const int REGENERATION_CREATION_COLOUR = Color.GREEN;
	protected static const vector DEBUG_VERTICAL_LINE = "0 30 0";

	protected static const float RECTANGULATION_SIZE = 50; // 50x50m rectangles - TODO: find a smart calculation?
	protected static const float HECTARE_CONVERSION_FACTOR = 0.0001; // x/10000
	protected static const float MIN_POSSIBLE_SCALE_VALUE = 0.001; // 1/1000 is a small enough tree scale
	protected static const string POINTDATA_CLASSNAME = ((typename)ForestGeneratorPointData).ToString();

	// TODO: generate top trees first THEN other layers
	protected static const int TREE_GROUPS_OFFSET_HACK = 10;

	protected static const int GRID_SIZE = 10; // 10 seems to be the best value here (tried 1, 20, 100)

	//------------------------------------------------------------------------------------------------
	//! \param[in] line
	//! \param[in] point
	//! \return
	protected bool OnLine(SCR_ForestGeneratorLine line, SCR_ForestGeneratorPoint point)
	{
		float a = Math.Max(line.p1.m_vPos[0], line.p2.m_vPos[0]);
		float b = Math.Min(line.p1.m_vPos[0], line.p2.m_vPos[0]);
		float c = Math.Max(line.p1.m_vPos[2], line.p2.m_vPos[2]);
		float d = Math.Min(line.p1.m_vPos[2], line.p2.m_vPos[2]);

		return
			point.m_vPos[0] <= a &&
			point.m_vPos[0] <= b &&
			point.m_vPos[2] <= c &&
			point.m_vPos[2] <= d;
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] a
	//! \param[in] b
	//! \param[in] c
	//! \return 0 for colinear, 2 for counter-clockwise, 1 for clockwise
	protected int Direction(SCR_ForestGeneratorPoint a, SCR_ForestGeneratorPoint b, SCR_ForestGeneratorPoint c)
	{
		int val =
			(b.m_vPos[2] - a.m_vPos[2]) * (c.m_vPos[0] - b.m_vPos[0]) -
			(b.m_vPos[0] - a.m_vPos[0]) * (c.m_vPos[2] - b.m_vPos[2]);

		if (val == 0)
			return 0; // colinear

		if (val < 0)
			return 2; // counter-clockwise direction

		return 1; // clockwise direction
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] line1
	//! \param[in] line2
	//! \return
	protected bool IsIntersect(SCR_ForestGeneratorLine line1, SCR_ForestGeneratorLine line2)
	{
		// four Direction for two lines and points of other line
		int dir1 = Direction(line1.p1, line1.p2, line2.p1);
		int dir2 = Direction(line1.p1, line1.p2, line2.p2);
		int dir3 = Direction(line2.p1, line2.p2, line1.p1);
		int dir4 = Direction(line2.p1, line2.p2, line1.p2);

		return
			(dir1 != dir2 && dir3 != dir4) ||			// they are intersecting
			(dir1 == 0 && OnLine(line1, line2.p1)) ||	// when p2 of line2 are on the line1
			(dir2 == 0 && OnLine(line1, line2.p2)) ||	// when p1 of line2 are on the line1
			(dir3 == 0 && OnLine(line2, line1.p1)) ||	// when p2 of line1 are on the line2
			(dir4 == 0 && OnLine(line2, line1.p2));		// when p1 of line1 are on the line2
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] line
	//! \param[in] rectangle
	//! \return
	protected bool IsIntersect(SCR_ForestGeneratorLine line, SCR_ForestGeneratorRectangle rectangle)
	{
		return
			IsIntersect(line, rectangle.m_Line1) ||
			IsIntersect(line, rectangle.m_Line2) ||
			IsIntersect(line, rectangle.m_Line3) ||
			IsIntersect(line, rectangle.m_Line4);
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] trees
	//! \param[in] groupIdx
	//! \param[in] type
	//! \param[in] debugGroupIdx
	//! \return
	protected bool PreprocessTreeArray(notnull array<ref ForestGeneratorTree> trees, int groupIdx, SCR_ETreeType type, int debugGroupIdx)
	{
		ForestGeneratorTree tree;
		float probaSum = 0;
		for (int i = trees.Count() - 1; i >= 0; --i)
		{
			tree = trees[i];
			if (tree.m_fWeight <= 0 || tree.m_Prefab.IsEmpty())
			{
				trees.RemoveOrdered(i);
			}
			else
			{
				probaSum += tree.m_fWeight;
				tree.m_iGroupIndex = groupIdx;
				tree.m_eType = type;
			}
		}

		if (probaSum > 0)
		{
			foreach (ForestGeneratorTree tree2 : trees)
			{
				tree2.m_fWeight = tree2.m_fWeight / probaSum;
			}
		}

		return !trees.IsEmpty();
	}

	//------------------------------------------------------------------------------------------------
	//!
	protected void PreprocessAllTrees()
	{
		int debugGroupIdx;
		foreach (ForestGeneratorLevel level : m_aLevels)
		{
			level.m_aGroupProbas = {};

			if (level.m_eType == SCR_EForestGeneratorLevelType.BOTTOM)
			{
				foreach (TreeGroupClass treeGroup : level.m_aTreeGroups)
				{
					PreprocessTreeArray(treeGroup.m_aTrees, 0, SCR_ETreeType.BOTTOM, debugGroupIdx);
				}
				continue;
			}

			// TOP or OUTLINE

			int groupIdx;
			float groupProbaSum;

			TreeGroupClass treeGroup;
			// cannot use foreach because editing the currently iterated array (yikes!)
			for (int i, groupCount = level.m_aTreeGroups.Count(); i < groupCount; i++)
			{
				treeGroup = level.m_aTreeGroups[i];

				if (treeGroup.m_fWeight > 0 &&
					treeGroup.m_aTrees &&
					!treeGroup.m_aTrees.IsEmpty() &&
					PreprocessTreeArray(treeGroup.m_aTrees, groupIdx, SCR_ETreeType.TOP, debugGroupIdx))
				{
					groupProbaSum += treeGroup.m_fWeight;
					groupIdx++;
					debugGroupIdx++;
				}
				else
				{
					level.m_aTreeGroups.RemoveOrdered(i);
					groupCount--;
					i--;
				}
			}

			foreach (TreeGroupClass treeGroup2 : level.m_aTreeGroups)
			{
				if (groupProbaSum > 0)
					treeGroup2.m_fWeight = treeGroup2.m_fWeight / groupProbaSum;

				level.m_aGroupProbas.Insert(treeGroup2.m_fWeight);
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Create a list of Forest Generator Points for each shape's vertices
	//! \param[in] shapeEntitySource an IEntitySource from a ShapeEntity (spline or polyline)
	//! \return created Forest Generator Points or null if the provided IEntitySource is not a shape (has no Points object array)
	protected array<ref SCR_ForestGeneratorPoint> GetClockWisePoints(notnull IEntitySource shapeEntitySource)
	{
		BaseContainerList points = shapeEntitySource.GetObjectArray("Points");
		if (!points)
			return null;

		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();

		array<ref SCR_ForestGeneratorPoint> result = {};

		BaseContainer point;
		vector pos;
		BaseContainerList dataArr;
		BaseContainer data;
		SCR_ForestGeneratorPoint genPoint;
		for (int i, pointCount = points.Count(); i < pointCount; i++)
		{
			point = points.Get(i);
			point.Get("Position", pos);

			bool smallOutline = true;
			bool middleOutline = true;
			dataArr = point.GetObjectArray("Data");

			bool hasPointData = false;
			for (int j, dataCount = dataArr.Count(); j < dataCount; ++j)
			{
				data = dataArr.Get(j);
				if (data.GetClassName() == POINTDATA_CLASSNAME)
				{
					data.Get("m_bSmallOutline", smallOutline);
					data.Get("m_bMiddleOutline", middleOutline);
					hasPointData = true;
					break;
				}
			}

			if (!hasPointData && worldEditorAPI && !worldEditorAPI.UndoOrRedoIsRestoring())
				worldEditorAPI.CreateObjectArrayVariableMember(point, null, "Data", POINTDATA_CLASSNAME, dataArr.Count());

			bool skip = false;
			foreach (SCR_ForestGeneratorPoint curPoint : result)
			{
				if (curPoint.m_vPos == pos)
				{
					Print("Found two points on the same position: " + pos + ", Skipping", LogLevel.WARNING);
					skip = true;
					break;
				}
			}

			if (skip)
				continue;

			genPoint = new SCR_ForestGeneratorPoint();
			pos[1] = 0;
			genPoint.m_vPos = pos;
			genPoint.m_bSmallOutline = smallOutline;
			genPoint.m_bMiddleOutline = middleOutline;

			result.Insert(genPoint);
		}

		// clockwise check
		int count = result.Count();
		if (count < 3)
			return result;

		int sum = 0;
		vector currentPoint;
		vector nextPoint;
		for (int i; i < count; i++)
		{
			currentPoint = result[i].m_vPos;
			if (i == count - 1)
				nextPoint = result[0].m_vPos;
			else
				nextPoint = result[i + 1].m_vPos;

			sum += (nextPoint[0] - currentPoint[0]) * (nextPoint[2] + currentPoint[2]);
		}

		if (sum < 0) // counter-clockwise, inverting points (reason unknown)
		{
			for (int i, iterNum = count * 0.5; i < iterNum; i++)
			{
				genPoint = result[i];
				result[i] = result[count - 1 - i];
				result[count - 1 - i] = genPoint;
			}
		}

		return result;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] points
	protected void FillOutlineLinesAndPoints(notnull array<ref SCR_ForestGeneratorPoint> points)
	{
		SCR_ForestGeneratorLine line;
		foreach (int i, SCR_ForestGeneratorPoint point : points)
		{
			if (i > 0)
			{
				line.p2 = point;
				line.m_fLength = (line.p2.m_vPos - line.p1.m_vPos).Length();
				point.m_Line1 = line;
				m_aLines.Insert(line);

				if (point.m_bSmallOutline)
					m_aSmallOutlinePoints.Insert(point);

				if (point.m_bMiddleOutline)
					m_aMiddleOutlinePoints.Insert(point);

				if (line.p1.m_bSmallOutline)
					m_aSmallOutlineLines.Insert(line);

				if (line.p1.m_bMiddleOutline)
					m_aMiddleOutlineLines.Insert(line);
			}

			line = new SCR_ForestGeneratorLine();
			line.p1 = point;
			point.m_Line2 = line;
		}

		SCR_ForestGeneratorPoint point = points[0];
		line.p2 = point;
		point.m_Line1 = line;
		line.m_fLength = (line.p2.m_vPos - line.p1.m_vPos).Length();
		m_aLines.Insert(line);

		if (point.m_bSmallOutline)
			m_aSmallOutlinePoints.Insert(point);

		if (point.m_bMiddleOutline)
			m_aMiddleOutlinePoints.Insert(point);

		if (line.p1.m_bSmallOutline)
			m_aSmallOutlineLines.Insert(line);

		if (line.p1.m_bMiddleOutline)
			m_aMiddleOutlineLines.Insert(line);
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] points
	protected void CalculateOutlineAnglesForPoints(notnull array<ref SCR_ForestGeneratorPoint> points)
	{
		int count = points.Count();
		if (count < 3)
			return;

		SCR_ForestGeneratorPoint previousPoint = points[count - 1];
		SCR_ForestGeneratorPoint currentPoint;
		SCR_ForestGeneratorPoint nextPoint;
		vector dir1;
		vector dir2;
		for (int i; i < count; i++)
		{
			currentPoint = points[i];

			if (i < count - 1)
				nextPoint = points[i + 1];
			else
				nextPoint = points[0];

			dir1 = previousPoint.m_vPos - currentPoint.m_vPos;
			dir2 = nextPoint.m_vPos - currentPoint.m_vPos;
			float yaw1 = dir1.ToYaw();
			float yaw2 = dir2.ToYaw();
			if (yaw1 > yaw2)
			{
				currentPoint.m_fMinAngle = yaw1 - 360;
				currentPoint.m_fMaxAngle = yaw2;
			}
			else
			{
				currentPoint.m_fMinAngle = yaw1;
				currentPoint.m_fMaxAngle = yaw2;
			}

			currentPoint.m_fAngle = Math.AbsFloat(currentPoint.m_fMaxAngle - currentPoint.m_fMinAngle);

			previousPoint = currentPoint;
		}
	}

	//------------------------------------------------------------------------------------------------
	protected override bool _WB_OnKeyChanged(BaseContainer src, string key, BaseContainerList ownerContainers, IEntity parent)
	{
		if (!super._WB_OnKeyChanged(src, key, ownerContainers, parent))
			return false;

		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();
		if (!worldEditorAPI || worldEditorAPI.UndoOrRedoIsRestoring())
			return true;

		src = worldEditorAPI.EntityToSource(this); // src is not fresh enough

		if (key == "m_bRegenerateEntireForest")
		{
			src.ClearVariable("m_bRegenerateEntireForest"); // don't save it to layers

			if (m_ParentShapeSource)
				RegenerateForest(true);
		}

		BaseContainerTools.WriteToInstance(this, src); // required for tree type changes to be considered without having to reload the world

		if (m_ParentShapeSource && key == "m_iSeed")
			RegenerateForest(true);

		return true;
	}

	//------------------------------------------------------------------------------------------------
	// triggers when a point is created/moved/deleted (or when a point data is edited!)
	protected override void OnShapeChangedInternal(IEntitySource shapeEntitySrc, ShapeEntity shapeEntity, array<vector> mins, array<vector> maxes)
	{
		super.OnShapeChangedInternal(shapeEntitySrc, shapeEntity, mins, maxes);
		RegenerateForest();
	}

	//------------------------------------------------------------------------------------------------
	// triggers when the generator is inserted in shape
	protected override void OnShapeInitInternal(IEntitySource shapeEntitySrc, ShapeEntity shapeEntity)
	{
		super.OnShapeInitInternal(shapeEntitySrc, shapeEntity);
		RegenerateForest(true);
	}

	//------------------------------------------------------------------------------------------------
	protected override void BeforeShapeTransformInternal(IEntitySource shapeEntitySrc, ShapeEntity shapeEntity, inout vector oldTransform[4])
	{
		super.BeforeShapeTransformInternal(shapeEntitySrc, shapeEntity, oldTransform);

		if (!m_bEntitiesFollowTerrainOnShapeMove)
			return;

		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();
		if (!worldEditorAPI)
			return;

		if (worldEditorAPI.UndoOrRedoIsRestoring())
			return;

		vector localPos, worldPos;
		vector parentPos;
		shapeEntitySrc.Get("coords", parentPos); // measurement has to be done on EntitySource, not Entity

		m_mEntitySourceATLHeights = new map<IEntitySource, float>();
		IEntitySource childSource;
		for (int i = m_Source.GetNumChildren() - 1; i >= 0; i--)
		{
			childSource = m_Source.GetChild(i);
			if (!childSource.Get("coords", localPos))
				continue;

			worldPos = localPos + parentPos;

			float yTerrain;
			if (!worldEditorAPI.TryGetTerrainSurfaceY(worldPos[0], worldPos[2], yTerrain))
				continue;

			m_mEntitySourceATLHeights.Insert(childSource, worldPos[1] - yTerrain);
		}
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnShapeTransformInternal(IEntitySource shapeEntitySrc, ShapeEntity shapeEntity, array<vector> mins, array<vector> maxes)
	{
		super.OnShapeTransformInternal(shapeEntitySrc, shapeEntity, mins, maxes);

		if (!m_bEntitiesFollowTerrainOnShapeMove)
			return;

		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();
		if (!worldEditorAPI)
			return;

		if (worldEditorAPI.UndoOrRedoIsRestoring())
			return;

		if (m_mEntitySourceATLHeights.IsEmpty())
			return;

		vector absPos = GetOrigin(); // assuming the generator stays at relative 0 0 0
		vector localPos, worldPos;

		foreach (IEntitySource childSource, float relativeY : m_mEntitySourceATLHeights)
		{
			if (!childSource.Get("coords", localPos))
				continue;

			worldPos = localPos + absPos;

			float yTerrain;
			if (!worldEditorAPI.TryGetTerrainSurfaceY(worldPos[0], worldPos[2], yTerrain))
				continue;

			float difference = relativeY - (worldPos[1] - yTerrain);
			if (difference != 0)
			{
				localPos[1] = localPos[1] + difference;
				worldEditorAPI.SetVariableValue(childSource, null, "coords", localPos.ToString(false));
			}
		}

		m_mEntitySourceATLHeights = null;
	}

	//------------------------------------------------------------------------------------------------
	// hack!!1!one waiting for BeforeShapeChangedInternal introduction
	protected override void OnPointChangedInternal(IEntitySource shapeEntitySrc, ShapeEntity shapeEntity, PointChangedSituation situation, int pointIndex, vector position)
	{
		super.OnPointChangedInternal(shapeEntitySrc, shapeEntity, situation, pointIndex, position);
		if (s_aPreviousPoints2D)
			return;

		array<vector> points3D = GetAnchorPoints(m_ParentShapeSource);
		s_aPreviousPoints2D = {};
		SCR_Math2D.Get2DPolygon(points3D, s_aPreviousPoints2D);
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] index
	//! \param[in] type
	//! \return
	protected int GetColorForTree(int index, SCR_ETreeType type)
	{
		const int colCount = 11;
		int colIdx = (5 * index + (int)type) % colCount; // 5 because 5 SCR_ETreeType types
		int color;
		switch (colIdx)
		{
			case 0:		color = 0xFF56E3D7; break;
			case 1:		color = 0xFF428AF5; break;
			case 2:		color = 0xFFF57542; break;
			case 3:		color = 0xFF8AE356; break;
			case 4:		color = 0xFF2F636B; break;
			case 5:		color = 0xFF818491; break;
			case 6:		color = 0xFFED9DBB; break;
			case 7:		color = 0xFF0009AB; break;
			case 8:		color = 0xFFAB003C; break;
			case 9:		color = 0xFFA8AB00; break;
			case 10:	color = 0xFFFFFFFF; break;
			default:	color = 0xFFFFFFFF; break;
		}
		return color;
	}

	//------------------------------------------------------------------------------------------------
	//! Empty now-useless arrays
	protected void MemoryCleanup()
	{
		// all these are apparently PopulateGrid-related
		m_aLines.Clear();
		m_aSmallOutlineLines.Clear();
		m_aMiddleOutlineLines.Clear();
		m_aRectangles.Clear();
		m_aOutlineRectangles.Clear();
		m_aSmallOutlinePoints.Clear();
		m_aMiddleOutlinePoints.Clear();
		m_aNonOutlineRectangles.Clear();
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] forceRegeneration
	protected void RegenerateForest(bool forceRegeneration = false)
	{
		if (!m_bEnableGeneration)
		{
			Print("Forest generation is disabled for this shape - tick it back on before saving", LogLevel.NORMAL);
			return;
		}

		float tick = System.GetTickCount(); // not Debug.BeginTimeMeasure because returns are on the way
		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();
		if (!worldEditorAPI)
		{
			Print("WorldEditorAPI is not available", LogLevel.ERROR);
			return;
		}

		if (worldEditorAPI.UndoOrRedoIsRestoring() || !worldEditorAPI.AreGeneratorEventsEnabled())
			return;

		SetSeed();

		// clear everything
		m_aSmallOutlinePoints.Clear();
		m_aMiddleOutlinePoints.Clear();
		m_aSmallOutlineLines.Clear();
		m_aMiddleOutlineLines.Clear();
		m_aOutlines.Clear();

		m_Grid = new ForestGeneratorGrid(GRID_SIZE);

		s_DebugShapeManager.Clear();

		Debug.BeginTimeMeasure();
		PreprocessAllTrees();
		Debug.EndTimeMeasure("Provided data preprocess");

		// load outlines
		float outlineWidthToClear; // outline or because scaling curves distance to clean
		ForestGeneratorOutline outline;
		foreach (ForestGeneratorLevel level : m_aLevels)
		{
			if (outlineWidthToClear < level.m_fOutlineScaleCurveDistance)
				outlineWidthToClear = level.m_fOutlineScaleCurveDistance;

			outline = ForestGeneratorOutline.Cast(level);
			if (!outline)
				continue;

			if (m_fMaxOutlinesWidth < outline.m_fMaxDistance)
				m_fMaxOutlinesWidth = outline.m_fMaxDistance;

			if (m_fMaxOutlinesWidth < outline.m_fMinDistance) // is this check even required?
				m_fMaxOutlinesWidth = outline.m_fMinDistance;

			m_aOutlines.Insert(outline);
		}

		if (outlineWidthToClear < m_fMaxOutlinesWidth)
			outlineWidthToClear = m_fMaxOutlinesWidth;

		array<ref SCR_ForestGeneratorPoint> generatorPoints = GetClockWisePoints(m_ParentShapeSource);
		if (!generatorPoints || generatorPoints.IsEmpty())
			return;

		Debug.BeginTimeMeasure();
		FillOutlineLinesAndPoints(generatorPoints);
		CalculateOutlineAnglesForPoints(generatorPoints);
		Debug.EndTimeMeasure("Outline point calculations");

		if (m_bPrintPerformanceDetails)
			s_Benchmark = new SCR_TimeMeasurementHelper();
		else
			s_Benchmark = null;

		// generate the forest

		// m_aShapePoints = GetTesselatedShapePoints(m_ParentShapeSource); // splines will be for later
		m_aShapePoints = GetAnchorPoints(m_ParentShapeSource);
		m_aShapePoints.Insert(m_aShapePoints[0]); // close the shape

		// see SCR_ObstacleDetector.GetPoints2D3D()
		array<vector> polygon3D = GetAnchorPoints(m_ParentShapeSource);
		array<float> polygon2D = {};
		SCR_Math2D.Get2DPolygon(polygon3D, polygon2D);

		Print("ForestGenerator - Populating grid", LogLevel.DEBUG);
		Debug.BeginTimeMeasure();
		PopulateGrid(polygon2D, polygon3D);
		Debug.EndTimeMeasure("ForestGenerator - Populating grid done");

		// create point -1 - old point - point +1 triangles
		// create point -1 - new point - point +1 triangles
		// what happens if a point is just deleted - regenerate everything?
		//		- try to find if deleted or moved (count points, other points moved or not, etc)
		//		- if only deleted, calculate triangle from previous point then new segment (-1,+1)'s middle
		//		- if cannot decide whether or not it was deleted or moved, recalculate everything

		SCR_ForestGeneratorOutlinePositionChecker outlinePositionChecker;

		if (forceRegeneration)
		{
			s_aPreviousPoints2D = {};
		}
		else
		{
			if (!s_aPreviousPoints2D) // should have been obtained by OnPointChangedInternal
			{
				Print("No previous points! Fallback on current points (this edit does not do anything)", LogLevel.WARNING);
				s_aPreviousPoints2D = polygon2D;
			}

			outlinePositionChecker = new SCR_ForestGeneratorOutlinePositionChecker(s_aPreviousPoints2D, polygon2D, outlineWidthToClear);
		}

		worldEditorAPI.BeginEditSequence(m_Source);

		Print("ForestGenerator - Deleting previous entities", LogLevel.DEBUG);
		Debug.BeginTimeMeasure();
		int entitiesCount = DeletePreviousEntities(polygon2D, outlinePositionChecker, forceRegeneration);
		Debug.EndTimeMeasure("ForestGenerator - Deleting " + entitiesCount + " previous entities done");

		Print("ForestGenerator - Generating entities", LogLevel.DEBUG);
		Debug.BeginTimeMeasure();
		entitiesCount = GenerateEntities(s_aPreviousPoints2D, outlinePositionChecker, forceRegeneration);
		Debug.EndTimeMeasure("ForestGenerator - Generating " + entitiesCount + " entities done");

		worldEditorAPI.EndEditSequence(m_Source);

		if (m_bPrintPerformanceDetails)
			s_Benchmark.PrintAllMeasures();

		s_aPreviousPoints2D = null;
		MemoryCleanup();

		int totalTime = System.GetTickCount(tick);
		float msPerEntity;
		float msPerSqMetre;
		if (entitiesCount > 0)
			msPerEntity = totalTime / entitiesCount;
		if (m_fArea > 0)
			msPerSqMetre = totalTime / m_fArea;

		PrintFormat(
			"Total time: %1 ms (~%2 ms/entity ratio / ~%3 ms/m²)",
			totalTime,
			msPerEntity.ToString(-1, 3),
			msPerSqMetre.ToString(-1, 3),
			level: LogLevel.NORMAL);
	}

	//------------------------------------------------------------------------------------------------
	//! Delete previous entities - either all of them for a full regeneration, or out of shape (hehe) ones for partial regeneration
	//! \param[in] currentPoints2D
	//! \param[in] outlineChecker
	//! \param[in] forceRegeneration
	//! \return
	protected int DeletePreviousEntities(notnull array<float> currentPoints2D, SCR_ForestGeneratorOutlinePositionChecker outlineChecker, bool forceRegeneration = false)
	{
		int result;
		if (forceRegeneration || !m_bAllowPartialRegeneration)
		{
			result = m_Source.GetNumChildren();
			DeleteAllChildren();
			return result;
		}

		// outline deletion

		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();
		IEntitySource entitySource;
		vector worldPos;
		vector entityPos;
		for (int i = m_Source.GetNumChildren() - 1; i >= 0; --i)
		{
			entitySource = m_Source.GetChild(i);
			worldPos = worldEditorAPI.SourceToEntity(entitySource).GetOrigin();
			entityPos = CoordToLocal(worldPos); // relative pos

			// remove everything not in the new shape
			if (!Math2D.IsPointInPolygon(currentPoints2D, entityPos[0], entityPos[2]))
			{
				worldEditorAPI.DeleteEntity(entitySource);
				continue;
			}

			// delete everything close to old and new impacted outlines
			if (outlineChecker.IsPosWithinSetDistance(entityPos))
			{
				if (m_bDrawDebugShapesRegeneration)
					s_DebugShapeManager.AddLine(worldPos, worldPos + DEBUG_VERTICAL_LINE, REGENERATION_DELETION_COLOUR);

				worldEditorAPI.DeleteEntity(entitySource);
				result++;
			}
		}

		return result;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] previousPoints2D
	//! \param[in] outlineChecker
	//! \param[in] forceRegeneration
	//! \return
	protected int GenerateEntities(notnull array<float> previousPoints2D, SCR_ForestGeneratorOutlinePositionChecker outlineChecker, bool forceRegeneration = false)
	{
		WorldEditorAPI worldEditorAPI = _WB_GetEditorAPI();

		BaseWorld world = worldEditorAPI.GetWorld();
		if (!world)
			return 0;

		// create new trees

		Debug.BeginTimeMeasure();
		RefreshObstacles();
		Debug.EndTimeMeasure("Obstacles scan");

		// draw obstacles
		if (m_bDrawDebugShapesObstacles)
		{
			foreach (SCR_ObstacleDetectorSplineInfo info : s_ObstacleDetector.GetObstacles())
			{
				if (info.m_fClearance == 0) // an area obstacle
				{
					s_DebugShapeManager.AddAABBRectangleXZ(info.m_vMinWithClearance, info.m_vMaxWithClearance);
				}
				else // a road-like obstacle
				{
					vector maxWithClearance;
					foreach (int index, vector minWithClearance : info.m_aMinsWithClearance)
					{
						maxWithClearance = info.m_aMaxsWithClearance[index];
						s_DebugShapeManager.AddAABBRectangleXZ(minWithClearance, maxWithClearance);
					}
				}
			}
		}

		bool partialGeneration = !forceRegeneration && m_bAllowPartialRegeneration && m_Source.GetNumChildren() > 0;

		bool useScaleCurve = m_fGlobalOutlineScaleCurveDistance > 0 && !m_aGlobalOutlineScaleCurve.IsEmpty();
		float scaleCurveDistanceDivisor;
		array<float> curveKnots;
		if (useScaleCurve)
		{
			// scaleCurveDistanceDivisor = 1 / m_fGlobalOutlineScaleCurveDistance;
			scaleCurveDistanceDivisor = SCALE_CURVE_RANGE / m_fGlobalOutlineScaleCurveDistance;
			// scaleCurveDistanceDivisor = 1;
			curveKnots = {};
			foreach (vector scalePoint : m_aGlobalOutlineScaleCurve)
			{
				curveKnots.Insert(scalePoint[0]);
			}
		}

		// init done

		int topLevelEntitiesCount, bottomLevelEntitiesCount;
		int smallOutlineEntitiesCount, middleOutlineEntitiesCount;
		int clusterEntitiesCount, otherEntitiesCount;
		int generatedEntitiesCount;
		int setVariableValueCalls;

		TraceParam traceParam = new TraceParam();
		traceParam.Flags = TraceFlags.WORLD;

		map<ResourceName, ref SCR_RandomisationEditorData> randomValuesMap = new map<ResourceName, ref SCR_RandomisationEditorData>();
		SCR_RandomisationEditorData randomisationData;
		SCR_ForestGeneratorTreeBase baseEntry;
		IEntitySource entitySource;
		vector entityMatrix[4];
		FallenTree fallenTree;
		WideForestGeneratorClusterObject wideObject;

		for (int i, count = m_Grid.GetEntryCount(); i < count; ++i)
		{
			vector worldPos;
			baseEntry = m_Grid.GetEntry(i, worldPos);
			if (!baseEntry.m_Prefab) // .IsEmpty()
				continue;

			worldPos[1] = world.GetSurfaceY(worldPos[0], worldPos[2]);							// snaps to ground here

			vector normalSamplePos = worldPos;
			vector terrainNormal = SCR_TerrainHelper.GetTerrainNormal(normalSamplePos, world);
			if (terrainNormal.LengthSq() < 0.001)
				terrainNormal = vector.Up;

			terrainNormal.Normalize();
			float slopeDeg = Math.Acos(Math.Clamp(terrainNormal[1], -1, 1)) * Math.RAD2DEG;

			vector localPos = CoordToLocal(worldPos);
			localPos[1] = localPos[1] + baseEntry.m_fVerticalOffset;

			if (partialGeneration) // TODO: move to Grid population instead?
			{
				if (
					Math2D.IsPointInPolygon(previousPoints2D, localPos[0], localPos[2]) &&		// if in the old shape
					!outlineChecker.IsPosWithinSetDistance(localPos)							// and not near a new outline
				)
					continue;
			}

			float scale = baseEntry.m_fScale;
			if (useScaleCurve && scale > 0)
			{
				float distanceFromShape = SCR_Math3D.GetDistanceFromSplineXZ(m_aShapePoints, localPos);
				if (distanceFromShape <= m_fGlobalOutlineScaleCurveDistance)
				{
					// (m_fOutlineScaleCurveDistance - distanceFromShape) because right-to-left curve reading
					float scaleFactor = LegacyCurve.Curve(ECurveType.CatmullRom, (m_fGlobalOutlineScaleCurveDistance - distanceFromShape) * scaleCurveDistanceDivisor, m_aGlobalOutlineScaleCurve, curveKnots)[1];

					if (scaleFactor < SCALE_CURVE_MIN_VALUE)
						scaleFactor = SCALE_CURVE_MIN_VALUE;
					else
					if (scaleFactor > SCALE_CURVE_MAX_VALUE)
						scaleFactor = SCALE_CURVE_MAX_VALUE;

					scale *= scaleFactor;
				}
			}

			if (scale < MIN_POSSIBLE_SCALE_VALUE)
			{
				PrintFormat("Avoiding near-zero scale tree (scale = %1 < %2)", scale, MIN_POSSIBLE_SCALE_VALUE, level: LogLevel.DEBUG);
				continue;
			}

			// vertical offset + burial along the terrain normal
			float burial = m_fSinkFactor * scale * (BURIAL_BASE + BURIAL_SLOPE * Math.Sin(slopeDeg * Math.DEG2RAD));
			localPos = CoordToLocal(worldPos + terrainNormal * (baseEntry.m_fVerticalOffset - burial));

			if (s_Benchmark)
				s_Benchmark.BeginMeasure("obstacleDetection");

			// providing a generated entities list would hinder performance here
			bool hasObstacle = s_ObstacleDetector.HasObstacle(worldPos);

			if (s_Benchmark)
				s_Benchmark.EndMeasure("obstacleDetection");

			if (hasObstacle)
				continue;

			if (partialGeneration)
			{
				if (m_bDrawDebugShapesRegeneration)
					s_DebugShapeManager.AddLine(worldPos, worldPos + DEBUG_VERTICAL_LINE, REGENERATION_CREATION_COLOUR);
			}

			if (s_Benchmark)
				s_Benchmark.BeginMeasure("createEntity");

			entitySource = worldEditorAPI.CreateEntity(baseEntry.m_Prefab, string.Empty, m_iSourceLayerID, m_Source, localPos, vector.Zero);

			if (s_Benchmark)
				s_Benchmark.EndMeasure("createEntity");

			generatedEntitiesCount++;
			switch (baseEntry.m_eType)
			{
				case SCR_ETreeType.TOP:				topLevelEntitiesCount++;		break;
				case SCR_ETreeType.BOTTOM:			bottomLevelEntitiesCount++;		break;
				case SCR_ETreeType.MIDDLE_OUTLINE:	middleOutlineEntitiesCount++;	break;
				case SCR_ETreeType.SMALL_OUTLINE:	smallOutlineEntitiesCount++;	break;
				case SCR_ETreeType.CLUSTER:			clusterEntitiesCount++;			break;
				default:							otherEntitiesCount++;			break;
			}

			if (m_bDrawDebugShapes)
				s_DebugShapeManager.AddSphere(worldPos, 1 + 5 - (int)baseEntry.m_eType, GetColorForTree(baseEntry.m_iGroupIndex, baseEntry.m_eType), ShapeFlags.NOOUTLINE);
				// 1 + 5 because 5x SCR_ETreeType types

			worldEditorAPI.SourceToEntity(entitySource).GetTransform(entityMatrix);

			if (s_Benchmark)
				s_Benchmark.BeginMeasure("editSequenceCalculation");

			float randomVerticalOffset;
			vector randomAngles; // pitch yaw roll
			bool alignToNormal;

			if (!randomValuesMap.Find(baseEntry.m_Prefab, randomisationData))
			{
				randomisationData = SCR_RandomisationEditorData.CreateFromEntitySource(entitySource);
				randomValuesMap.Insert(baseEntry.m_Prefab, randomisationData);
			}

			if (randomisationData)
			{
				randomVerticalOffset = SafeRandomFloatInclusive(randomisationData.m_vRandomVertOffset[0], randomisationData.m_vRandomVertOffset[1]);

				randomAngles[0] = SafeRandomFloatInclusive(-randomisationData.m_fRandomPitchAngle, randomisationData.m_fRandomPitchAngle);
				randomAngles[1] = SafeRandomFloatInclusive(0, 360);
				randomAngles[2] = SafeRandomFloatInclusive(-randomisationData.m_fRandomRollAngle, randomisationData.m_fRandomRollAngle);

				alignToNormal = randomisationData.m_bAlignToNormal;
			}
			else
			{
				if (baseEntry.m_fVerticalOffset > 0)
					randomVerticalOffset = SafeRandomFloatInclusive(-baseEntry.m_fVerticalOffset, baseEntry.m_fVerticalOffset);

				if (baseEntry.m_fRandomPitchAngle > 0)
					randomAngles[0] = SafeRandomFloatInclusive(-baseEntry.m_fRandomPitchAngle, baseEntry.m_fRandomPitchAngle);

				randomAngles[1] = SafeRandomFloatInclusive(0, 360);

				if (baseEntry.m_fRandomRollAngle > 0)
					randomAngles[2] = SafeRandomFloatInclusive(-baseEntry.m_fRandomRollAngle, baseEntry.m_fRandomRollAngle);

				// alignToNormal = false;
			}

			fallenTree = FallenTree.Cast(baseEntry);
			wideObject = WideForestGeneratorClusterObject.Cast(baseEntry);

			if (wideObject)
				alignToNormal = wideObject.m_bAlignToNormal;
			else
			if (fallenTree)
				alignToNormal = fallenTree.m_bAlignToNormal;

			// yaw: long axis across the slope (follows the contour) for a share of the rocks
			if (slopeDeg >= CONTOUR_MIN_SLOPE && m_RandomGenerator.RandFloat01() < CONTOUR_SHARE)
			{
				vector downhill = Vector(terrainNormal[0], 0, terrainNormal[2]);
				if (downhill.LengthSq() > 0.000001)
				{
					downhill.Normalize();
					float contourYaw = downhill.ToYaw() + 90;
					if (m_RandomGenerator.RandFloat01() < 0.5)
						contourYaw += 180;

					randomAngles[1] = contourYaw + SafeRandomFloatInclusive(-CONTOUR_SPREAD, CONTOUR_SPREAD);
				}
			}

			if (m_fTerrainNormalFactor > 0)
				alignToNormal = true;

			if (randomAngles[1] != 0) // yaw first
				SCR_Math3D.RotateAround(entityMatrix, entityMatrix[3], entityMatrix[1], -Math.DEG2RAD * randomAngles[1], entityMatrix);

			if (randomAngles[0] != 0)
				SCR_Math3D.RotateAround(entityMatrix, entityMatrix[3], entityMatrix[0], -Math.DEG2RAD * randomAngles[0], entityMatrix);

			if (randomAngles[2] != 0)
				SCR_Math3D.RotateAround(entityMatrix, entityMatrix[3], entityMatrix[2], -Math.DEG2RAD * randomAngles[2], entityMatrix);

			if (alignToNormal)
			{
				float normalFactor = m_fTerrainNormalFactor;
				if (normalFactor <= 0)
					normalFactor = 1; // alignment requested by the prefab / cluster object flags

				vector normal = vector.Up * (1 - normalFactor) + terrainNormal * normalFactor;
				if (normal.LengthSq() > 0.001)
				{
					normal.Normalize();
					entityMatrix[1] = normal;													// newUp
					entityMatrix[0] = (entityMatrix[1] * entityMatrix[2]).Normalized();		// newRight
					entityMatrix[2] = (entityMatrix[0] * entityMatrix[1]).Normalized();		// newForward
				}
			}

			vector angles = Math3D.MatrixToAngles(entityMatrix);

			if (s_Benchmark)
				s_Benchmark.EndMeasure("editSequenceCalculation");

			if (s_Benchmark)
				s_Benchmark.BeginMeasure("editSequence");

			if (angles != vector.Zero || scale != 1)
			{
				worldEditorAPI.BeginEditSequence(entitySource);

				if (angles != vector.Zero)
					worldEditorAPI.SetVariableValue(entitySource, null, "angles", string.Format("%1 %2 %3", angles[1], angles[0], angles[2]));

				if (scale != 1)
					worldEditorAPI.SetVariableValue(entitySource, null, "scale", scale.ToString());

				worldEditorAPI.EndEditSequence(entitySource);
			}

			if (s_Benchmark)
				s_Benchmark.EndMeasure("editSequence");
		}

		ClearObstacles(); // frees RAM

		if (m_bPrintArea)
			Print("Area of the polygon is: " + m_fArea.ToString(lenDec: 2) + " square meters", LogLevel.NORMAL);

		if (m_bPrintEntitiesCount)
		{
			Print("Forest generator generated: " + topLevelEntitiesCount + " entities in top level", LogLevel.NORMAL);
			Print("Forest generator generated: " + bottomLevelEntitiesCount + " entities in bottom level", LogLevel.NORMAL);
			Print("Forest generator generated: " + middleOutlineEntitiesCount + " entities in middle outline", LogLevel.NORMAL);
			Print("Forest generator generated: " + smallOutlineEntitiesCount + " entities in small outline", LogLevel.NORMAL);
			Print("Forest generator generated: " + clusterEntitiesCount + " entities in clusters", LogLevel.NORMAL);
			if (otherEntitiesCount > 0)
				Print("Forest generator generated: " + clusterEntitiesCount + " uncategorised entities", LogLevel.WARNING);

			Print("Forest generator generated: " + generatedEntitiesCount + " entities in total (" + setVariableValueCalls + " WE API calls)", LogLevel.NORMAL);
		}

		return generatedEntitiesCount;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] polygon2D
	//! \param[in] polygon3D
	protected void PopulateGrid(array<float> polygon2D, array<vector> polygon3D)
	{
		m_Grid.Clear();
		m_aGridEntries.Clear();

		m_fArea = SCR_Math2D.GetPolygonArea(polygon2D);

		SCR_AABB bbox = new SCR_AABB(polygon3D);
		m_Grid.Resize(bbox.m_vDimensions[0], bbox.m_vDimensions[2]);

		Debug.BeginTimeMeasure();
		Rectangulate(bbox, polygon2D);
		Debug.EndTimeMeasure("ForestGenerator - Rectangulation done");

		vector worldMat[4];
		GetWorldTransform(worldMat);
		vector bboxMin = bbox.m_vMin;
		vector bboxMinWorld = bboxMin.Multiply4(worldMat);
		m_Grid.SetPointOffset(bboxMinWorld[0], bboxMinWorld[2]);

		Debug.BeginTimeMeasure();
		m_iStatsTested = 0;
		m_iStatsRejectedPhysical = 0;
		m_iStatsRejectedProbability = 0;

		GenerateForestGeneratorTrees(polygon2D, bbox);

		if (m_bPrintTerrainStats)
			PrintFormat("RockDebris terrain rules: %1 tested, rejected by physical slope limit %2, by steep-slope density %3", m_iStatsTested, m_iStatsRejectedPhysical, m_iStatsRejectedProbability, level: LogLevel.NORMAL);
		Debug.EndTimeMeasure("ForestGenerator - Grid tree generation done");
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] bbox
	//! \param[in] polygon2D
	protected void Rectangulate(notnull SCR_AABB bbox, notnull array<float> polygon2D)
	{
		vector direction = bbox.m_vMax - bbox.m_vMin;
		float targetRectangleWidth = RECTANGULATION_SIZE;
		float targetRectangleLength = RECTANGULATION_SIZE;
		int targetRectangleCountW = Math.Ceil(direction[0] / targetRectangleWidth);
		int targetRectangleCountL = Math.Ceil(direction[2] / targetRectangleLength);

		vector ownerOrigin = GetOrigin();

		SCR_ForestGeneratorRectangle rectangle;
		vector p1;
		Shape shape;
		for (int x; x < targetRectangleCountW; x++)
		{
			for (int y; y < targetRectangleCountL; y++)
			{
				bool isInPolygon = false;

				rectangle = new SCR_ForestGeneratorRectangle();
				rectangle.m_iX = x;
				rectangle.m_iY = y;
				rectangle.m_fWidth = targetRectangleWidth;
				rectangle.m_fLength = targetRectangleLength;
				rectangle.m_fArea = rectangle.m_fLength * rectangle.m_fWidth;
				p1 = bbox.m_vMin;
				p1[0] = p1[0] + (x * targetRectangleWidth);
				p1[2] = p1[2] + (y * targetRectangleLength);
				rectangle.m_Line4.p2.m_vPos = p1;
				rectangle.m_Line1.p1.m_vPos = p1;
				if (!isInPolygon)
					isInPolygon = Math2D.IsPointInPolygon(polygon2D, p1[0], p1[2]);

				rectangle.m_aPoints.Insert(p1);

				p1[0] = p1[0] + targetRectangleWidth;
				rectangle.m_Line1.p2.m_vPos = p1;
				rectangle.m_Line2.p1.m_vPos = p1;
				if (!isInPolygon)
					isInPolygon = Math2D.IsPointInPolygon(polygon2D, p1[0], p1[2]);

				rectangle.m_aPoints.Insert(p1);

				p1[2] = p1[2] + targetRectangleLength;
				rectangle.m_Line2.p2.m_vPos = p1;
				rectangle.m_Line3.p1.m_vPos = p1;
				if (!isInPolygon)
					isInPolygon = Math2D.IsPointInPolygon(polygon2D, p1[0], p1[2]);

				rectangle.m_aPoints.Insert(p1);

				p1[0] = p1[0] - targetRectangleWidth;
				rectangle.m_Line3.p2.m_vPos = p1;
				rectangle.m_Line4.p1.m_vPos = p1;
				if (!isInPolygon)
					isInPolygon = Math2D.IsPointInPolygon(polygon2D, p1[0], p1[2]);

				rectangle.m_aPoints.Insert(p1);

				foreach (SCR_ForestGeneratorLine line : m_aLines)
				{
					if (!NeedsCheck(line, rectangle) || !IsIntersect(line, rectangle))
						continue;

					bool found = false;
					foreach (SCR_ForestGeneratorLine rectLine : rectangle.m_aLines)
					{
						if (rectLine == line)
						{
							found = true;
							break;
						}
					}

					if (!found)
						rectangle.m_aLines.Insert(line);
				}

				bool areLinesEmpty = rectangle.m_aLines.IsEmpty();
				if (areLinesEmpty && !isInPolygon)
					continue;

				m_aRectangles.Insert(rectangle);

				if (areLinesEmpty)
					m_aNonOutlineRectangles.Insert(rectangle);
				else
					m_aOutlineRectangles.Insert(rectangle);

				if (m_bDrawDebugShapesRectangulation)
				{
					int red;
					int green;
					int blue;
					if (areLinesEmpty)
					{
						green = Math.Floor(m_RandomGenerator.RandFloatXY(0, 255));
						blue = Math.Floor(m_RandomGenerator.RandFloatXY(0, 255));
					}
					else
					{
						red = 255;
					}

					s_DebugShapeManager.AddBBox(ownerOrigin + rectangle.m_Line1.p1.m_vPos, ownerOrigin + rectangle.m_Line3.p1.m_vPos, ARGB(63, red, green, blue));
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] line
	//! \param[in] rectangle
	//! \return
	protected bool NeedsCheck(SCR_ForestGeneratorLine line, SCR_ForestGeneratorRectangle rectangle)
	{
		vector linePoint1 = line.p1.m_vPos;
		vector linePoint2 = line.p2.m_vPos;
		vector mins;
		vector maxs;
		rectangle.GetBounds(mins, maxs);

		float linePoint1x = linePoint1[0];
		float linePoint1z = linePoint1[2];
		float linePoint2x = linePoint2[0];
		float linePoint2z = linePoint2[2];
		float minsx = mins[0];
		float minsz = mins[2];
		float maxsx = maxs[0];
		float maxsz = maxs[2];

		if (
			(linePoint1x < minsx && linePoint2x < minsx) ||
			(linePoint1x > maxsx && linePoint2x > maxsx) ||
			(linePoint1z < minsz && linePoint2z < minsz) ||
			(linePoint1z > maxsz && linePoint2z > maxsz))
			return false;

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] polygon2D
	//! \param[in] bbox
	protected void GenerateForestGeneratorTrees(array<float> polygon2D, SCR_AABB bbox)
	{
		if (bbox.m_vDimensions[0] * bbox.m_vDimensions[2] <= 0.01) // too small area
			return;

		// clusters
		foreach (ForestGeneratorCluster cluster : m_aClusters)
		{
			if (!cluster.m_bGenerate || cluster.m_fRadius <= 0)
				continue;

			if (cluster.m_Type == SCR_EForestGeneratorClusterType.CIRCLE)
				GenerateCircleCluster(ForestGeneratorCircleCluster.Cast(cluster), polygon2D, bbox);
			else
			if (cluster.m_Type == SCR_EForestGeneratorClusterType.STRIP)
				GenerateStripCluster(ForestGeneratorStripCluster.Cast(cluster), polygon2D, bbox);
		}

		// then trees
		foreach (ForestGeneratorLevel level : m_aLevels)
		{
			if (!level.m_bGenerate)
				continue;

			switch (level.m_eType)
			{
				case SCR_EForestGeneratorLevelType.TOP:
					GenerateTopTrees(polygon2D, bbox, ForestGeneratorTopLevel.Cast(level));
					break;

				case SCR_EForestGeneratorLevelType.OUTLINE:
					GenerateOutlineTrees(polygon2D, bbox, ForestGeneratorOutline.Cast(level));
					break;

				case SCR_EForestGeneratorLevelType.BOTTOM:
					GenerateBottomTrees(polygon2D, bbox, ForestGeneratorBottomLevel.Cast(level));
					break;
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] center
	//! \param[in] radius
	//! \param[out] rectangles
	//! \return
	protected int FindRectanglesInCircle(vector center, float radius, out array<SCR_ForestGeneratorRectangle> rectangles)
	{
		int count = 0;
		float deltaX, deltaY;
		float radiusSq = radius * radius;

		foreach (SCR_ForestGeneratorRectangle rectangle : m_aRectangles)
		{
			foreach (vector point : rectangle.m_aPoints)
			{
				deltaX = center[0] - Math.Max(rectangle.m_Line1.p1.m_vPos[0], Math.Min(center[0], rectangle.m_Line1.p1.m_vPos[0] + rectangle.m_fWidth));
				deltaY = center[2] - Math.Max(rectangle.m_Line1.p1.m_vPos[2], Math.Min(center[2], rectangle.m_Line1.p1.m_vPos[2] + rectangle.m_fLength));

				if (deltaX * deltaX + deltaY * deltaY < radiusSq)
				{
					rectangles.Insert(rectangle);
					count++;
				}
			}
		}

		return count;
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] polygon2D
	//! \param[in] bbox
	//! \param[out] clusterCenter
	//! \param[in] additionalDistance
	//! \param[in] allowInForest
	//! \param[in] allowInOutline
	//! \return
	protected bool GetClusterPoint(notnull array<float> polygon2D, notnull SCR_AABB bbox, out vector clusterCenter, float additionalDistance, bool allowInForest, bool allowInOutline)
	{
		if (!allowInForest && !allowInOutline)
			return false;

		if (allowInForest && allowInOutline)
		{
			clusterCenter = m_RandomGenerator.GenerateRandomPoint(polygon2D, bbox.m_vMin, bbox.m_vMax);
			return true;
		}

		array<bool> inOutlineList;
		if (allowInOutline)
			inOutlineList = {};

		array<SCR_ForestGeneratorRectangle> rectangles = {};
		for (int i; i < MAX_CLUSTER_ATTEMPT; ++i)
		{
			bool stopThisAttempt;

			vector possibleLocation = m_RandomGenerator.GenerateRandomPoint(polygon2D, bbox.m_vMin, bbox.m_vMax);
			rectangles.Clear();

			int rectanglesCount = FindRectanglesInCircle(possibleLocation, additionalDistance + m_fMaxOutlinesWidth, rectangles);
			if (allowInOutline)
			{
				inOutlineList.Clear();
				inOutlineList.Reserve(rectanglesCount);
			}

			foreach (SCR_ForestGeneratorRectangle rectangle : rectangles)
			{
				bool isInOutline = IsInOutline(rectangle, possibleLocation, additionalDistance);
				if (isInOutline && allowInForest) // "forest only" has absolutely NO presence in outline
				{
					stopThisAttempt = true;
					break;
				}

				if (allowInOutline)
					inOutlineList.Insert(isInOutline);
			}

			if (stopThisAttempt)
				continue;

			if (allowInForest											// attempt was not skipped, all checks were outside outline
				|| (allowInOutline && inOutlineList.Contains(true)))	// only one point in outline is acceptable
			{
				clusterCenter = possibleLocation; // set the out value once
				return true;
			}
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! Terrain slope [degrees] at a world position from central height differences
	protected float GetSlopeAt(float x, float z)
	{
		BaseWorld world = GetWorld();
		float d = 1.5;
		float dx = (world.GetSurfaceY(x + d, z) - world.GetSurfaceY(x - d, z)) / (2 * d);
		float dz = (world.GetSurfaceY(x, z + d) - world.GetSurfaceY(x, z - d)) / (2 * d);
		return Math.Atan2(Math.Sqrt(dx * dx + dz * dz), 1) * Math.RAD2DEG;
	}

	//------------------------------------------------------------------------------------------------
	//! 0..1: how much this spot looks like the foot of a steeper slope (talus / erosion deposit zone).
	//! Looks for higher ground within the runout distance in 8 directions and compares its slope to the local one.
	protected float GetErosionScore(vector pointWorld)
	{
		float height = GetWorld().GetSurfaceY(pointWorld[0], pointWorld[2]);
		float localSlope = GetSlopeAt(pointWorld[0], pointWorld[2]);

		float maxSourceSlope = 0;
		for (int ring = 1; ring <= 3; ring++)
		{
			float distance = EROSION_RUNOUT * ring / 3;
			for (int dir; dir < 8; dir++)
			{
				float angle = dir * 45 * Math.DEG2RAD;
				float qx = pointWorld[0] + Math.Sin(angle) * distance;
				float qz = pointWorld[2] + Math.Cos(angle) * distance;

				if (GetWorld().GetSurfaceY(qx, qz) < height + 0.3) // only ground above us can shed material onto us
					continue;

				float sourceSlope = GetSlopeAt(qx, qz);
				if (sourceSlope > maxSourceSlope)
					maxSourceSlope = sourceSlope;
			}
		}

		return Math.Clamp((maxSourceSlope - localSlope - EROSION_MIN_DELTA) / (EROSION_FULL_DELTA - EROSION_MIN_DELTA), 0, 1);
	}

	//------------------------------------------------------------------------------------------------
	//! GetClusterPoint, but prefers (never forces) loose accumulation zones and the foot of steeper slopes.
	//! Centres are re-rolled with a soft acceptance chance; if none is accepted a plain random centre is used,
	//! so no area is ever emptied and the total cluster count stays the same.
	protected bool GetBiasedClusterPoint(notnull array<float> polygon2D, notnull SCR_AABB bbox, out vector clusterCenter, float additionalDistance, bool allowInForest, bool allowInOutline)
	{
		m_fClusterBoost = 1;

		vector worldMat[4];
		GetWorldTransform(worldMat);

		float erosionFloor = Math.Clamp(1 - EROSION_FLOOR_PER_FACTOR * m_fErosionFactor, 0.1, 1);

		for (int attempt; attempt < ZONE_ATTEMPTS; attempt++)
		{
			if (!GetClusterPoint(polygon2D, bbox, clusterCenter, additionalDistance, allowInForest, allowInOutline))
				return false;

			vector worldCentre = clusterCenter.Multiply4(worldMat);
			float noise = PatchNoise(worldCentre[0], worldCentre[2], ZONE_NOISE_SIZE, 7);
			float keep = Math.Lerp(ZONE_NOISE_FLOOR, 1, noise);

			float erosion;
			if (m_fErosionFactor > 0)
			{
				erosion = GetErosionScore(worldCentre);
				keep = keep * Math.Lerp(erosionFloor, 1, erosion);
			}

			if (m_RandomGenerator.RandFloat01() < keep)
			{
				m_fClusterBoost = 1 + EROSION_COUNT_BOOST * m_fErosionFactor * erosion;
				return true;
			}
		}

		return GetClusterPoint(polygon2D, bbox, clusterCenter, additionalDistance, allowInForest, allowInOutline);
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] cluster
	//! \param[in] polygon2D
	//! \param[in] bbox
	protected void GenerateCircleCluster(notnull ForestGeneratorCircleCluster cluster, notnull array<float> polygon2D, notnull SCR_AABB bbox)
	{
		vector worldMat[4];
		GetWorldTransform(worldMat);

		float CDENSHA = SafeRandomFloatInclusive(cluster.m_fMinCDENSHA, cluster.m_fMaxCDENSHA);

		vector clusterCenter;
		vector pointLocal;
		SmallForestGeneratorClusterObject newClusterObject;
		vector point;
		WideForestGeneratorClusterObject wideObject;
		for (int c, clusterCount = Math.Ceil(m_fArea * HECTARE_CONVERSION_FACTOR * CDENSHA); c < clusterCount; c++)
		{
			bool allowInForest = cluster.m_iPlacementArea != 2;
			bool allowInOutline = cluster.m_iPlacementArea != 1;
			if (!GetBiasedClusterPoint(polygon2D, bbox, clusterCenter, cluster.m_fRadius, allowInForest, allowInOutline))
				continue;

			bool isPolygonCheckUseless = !SCR_Math3D.IsPointWithinSplineDistanceXZ(m_aShapePoints, clusterCenter, cluster.m_fRadius);

			foreach (SmallForestGeneratorClusterObject clusterObject : cluster.m_aObjects)
			{
				for (int o, objectCount = GetClusterObjectCount(clusterObject); o < objectCount; o++)
				{
					pointLocal = GeneratePointInCircle(clusterObject.m_fMinRadius, clusterObject.m_fMaxRadius, clusterCenter);
					if (isPolygonCheckUseless || Math2D.IsPointInPolygon(polygon2D, pointLocal[0], pointLocal[2]))
					{
						if (s_Benchmark)
							s_Benchmark.BeginMeasure("clone");

						newClusterObject = SmallForestGeneratorClusterObject.Cast(clusterObject.Clone());

						if (s_Benchmark)
							s_Benchmark.EndMeasure("clone");

						if (!newClusterObject)
							continue;

						m_aGridEntries.Insert(newClusterObject);
						point = pointLocal.Multiply4(worldMat);

						SetObjectScale(newClusterObject);

						if (!ApplyTerrainRules(newClusterObject, point))
							continue;

						wideObject = WideForestGeneratorClusterObject.Cast(newClusterObject);
						if (wideObject)
						{
							wideObject.m_fYaw = m_RandomGenerator.RandFloat01() * 360;
							wideObject.Rotate();
						}

						if (m_Grid.IsColliding(point, newClusterObject))
							continue;

						newClusterObject.m_eType = SCR_ETreeType.CLUSTER;
						m_Grid.AddEntry(newClusterObject, point);
					}
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] cluster
	//! \param[in] polygon2D
	//! \param[in] bbox
	protected void GenerateStripCluster(notnull ForestGeneratorStripCluster cluster, notnull array<float> polygon2D, notnull SCR_AABB bbox)
	{
		vector worldMat[4];
		GetWorldTransform(worldMat);

		vector direction = vector.FromYaw(m_RandomGenerator.RandFloatXY(0, 360));
		vector perpendicular;
		perpendicular[0] = direction[2];
		perpendicular[2] = -direction[0];

		float CDENSHA = SafeRandomFloatInclusive(cluster.m_fMinCDENSHA, cluster.m_fMaxCDENSHA);

		vector clusterCenter;
		vector pointLocal;
		vector offset;
		vector point;
		SmallForestGeneratorClusterObject newClusterObject;
		WideForestGeneratorClusterObject wideObject;
		for (int c, clusterCount = Math.Ceil(m_fArea * HECTARE_CONVERSION_FACTOR * CDENSHA); c < clusterCount; c++)
		{
			bool allowInForest = cluster.m_iPlacementArea != 2;
			bool allowInOutline = cluster.m_iPlacementArea != 1;
			if (!GetBiasedClusterPoint(polygon2D, bbox, clusterCenter, cluster.m_fRadius, allowInForest, allowInOutline))
				continue;

			bool isPolygonCheckUseless = !SCR_Math3D.IsPointWithinSplineDistanceXZ(m_aShapePoints, clusterCenter, cluster.m_fRadius);

			foreach (SmallForestGeneratorClusterObject clusterObject : cluster.m_aObjects)
			{
				for (int o, objectCount = GetClusterObjectCount(clusterObject); o < objectCount; o++)
				{
					float distance = SafeRandomFloatInclusive(clusterObject.m_fMinRadius, clusterObject.m_fMaxRadius);
					int rnd = m_RandomGenerator.RandIntInclusive(0, 1);

					if (rnd == 0)
						distance = -distance;

					float y01 = distance / cluster.m_fRadius * cluster.m_fFrequency;
					float ySin = Math.Sin(y01 * 360 * Math.DEG2RAD);
					float y = ySin * cluster.m_fAmplitude;

					offset = vector.Zero;
					offset[0] = SafeRandomFloatInclusive(0, cluster.m_fMaxXOffset);
					offset[2] = SafeRandomFloatInclusive(0, cluster.m_fMaxYOffset);
					pointLocal = (direction * distance) + (y * perpendicular) + clusterCenter + offset;

					if (isPolygonCheckUseless || Math2D.IsPointInPolygon(polygon2D, pointLocal[0], pointLocal[2]))
					{
						if (s_Benchmark)
							s_Benchmark.BeginMeasure("clone");

						newClusterObject = SmallForestGeneratorClusterObject.Cast(clusterObject.Clone());

						if (s_Benchmark)
							s_Benchmark.EndMeasure("clone");

						if (!newClusterObject)
							continue;

						m_aGridEntries.Insert(newClusterObject);
						point = pointLocal.Multiply4(worldMat);

						SetObjectScale(newClusterObject);

						if (!ApplyTerrainRules(newClusterObject, point))
							continue;

						wideObject = WideForestGeneratorClusterObject.Cast(newClusterObject);
						if (wideObject)
						{
							wideObject.m_fYaw = m_RandomGenerator.RandFloatXY(0, 360);
							wideObject.Rotate();
						}

						if (m_Grid.IsColliding(point, newClusterObject))
							continue;

						newClusterObject.m_eType = SCR_ETreeType.CLUSTER;
						m_Grid.AddEntry(newClusterObject, point);
					}
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] clusterObject
	//! \return
	protected int GetClusterObjectCount(notnull SmallForestGeneratorClusterObject clusterObject)
	{
		string prefabPath = clusterObject.m_Prefab;
		float amount = m_fRockAmount;
		if (prefabPath.Contains(DEBRIS_KEYWORD))
			amount = m_fDebrisAmount;

		float scaled = GetBaseClusterObjectCount(clusterObject) * amount * m_fClusterBoost;
		int result = Math.Floor(scaled);
		if (m_RandomGenerator.RandFloat01() < scaled - result) // stochastic rounding so 0.4 means "40% of the time one"
			result++;

		return result;
	}

	//------------------------------------------------------------------------------------------------
	//! Authored count (before amount factors)
	protected int GetBaseClusterObjectCount(notnull SmallForestGeneratorClusterObject clusterObject)
	{
		int min = clusterObject.m_iMinCount;
		int max = clusterObject.m_iMaxCount;
		if (min == max)
			return min;

		if (min > max)
		{
			int tmp = min;
			min = max;
			max = tmp;
			Print("A forest generator's cluster has Min Count > Max Count at " + GetOrigin(), LogLevel.WARNING);
		}

		if (clusterObject.m_iRandomMidPercent < 0)
			return m_RandomGenerator.RandIntInclusive(min, max);

		// Gaussian curve, here we come

		float mid = min + (max - min) * clusterObject.m_iRandomMidPercent * 0.01;
		return GetGaussianDistributionRandomIntInclusive(min, mid, max);
	}

	//------------------------------------------------------------------------------------------------
	//! SCR_Math.GetGaussianDistributionRandom but we use our own random generator and round the result
	//! \param[in] min (included)
	//! \param[in] mid Gaussian curve's middle point
	//! \param[in] max (included)
	//! \return
	protected int GetGaussianDistributionRandomIntInclusive(int min, float mid, int max)
	{
		float result = m_RandomGenerator.RandGaussFloat((max - min) / 6.0, mid); // ~99.73% cases covered

		if (result < min)
			return min;

		if (result > max)
			return max;

		return Math.Round(result);
	}

	//------------------------------------------------------------------------------------------------
	//! Get a random value between min and max, if min > max they are reversed
	//! \param[in] min
	//! \param[in] max
	//! \return
	protected float SafeRandomFloatInclusive(float min, float max)
	{
		if (min == max)
			return max;

		if (min < max)
			return m_RandomGenerator.RandFloatXY(min, max);

		Print("A forest generator object has some min value > max value at " + GetOrigin(), LogLevel.WARNING);
		return m_RandomGenerator.RandFloatXY(max, min);
	}

	//------------------------------------------------------------------------------------------------
	//! Density is more important at the centre (random 0-radius)
	//! \param[in] innerRadius
	//! \param[in] outerRadius
	//! \param[in] circleCenter
	//! \return
	protected vector GeneratePointInCircle(float innerRadius, float outerRadius, vector circleCenter)
	{
		vector direction = vector.FromYaw(m_RandomGenerator.RandFloatXY(0, 360));
		float rand = SafeRandomFloatInclusive(innerRadius, outerRadius);
		return circleCenter + rand * direction;
	}

	//------------------------------------------------------------------------------------------------
	//! Density is more important at the centre (random 0-radius)
	//! \param[in] innerRadius
	//! \param[in] outerRadius
	//! \param[in] point
	//! \return
	protected vector GeneratePointInCircle(float innerRadius, float outerRadius, SCR_ForestGeneratorPoint point)
	{
		vector direction = vector.FromYaw(m_RandomGenerator.RandFloatXY(point.m_fMinAngle, point.m_fMaxAngle));
		float rand = SafeRandomFloatInclusive(innerRadius, outerRadius);
		return point.m_vPos + rand * direction;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] rectangle
	//! \return
	protected vector GenerateRandomPointInRectangle(notnull SCR_ForestGeneratorRectangle rectangle)
	{
		return {
			m_RandomGenerator.RandFloat01() * rectangle.m_fWidth + rectangle.m_Line1.p1.m_vPos[0],
			0,
			m_RandomGenerator.RandFloat01() * rectangle.m_fLength + rectangle.m_Line1.p1.m_vPos[2]
		};
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] treeGroups
	//! \return
	protected bool GetIsAnyTreeValid(notnull array<ref TreeGroupClass> treeGroups)
	{
		foreach (TreeGroupClass treeGroup : treeGroups)
		{
			if (treeGroup.m_fWeight <= 0)
				continue;

			foreach (ForestGeneratorTree tree : treeGroup.m_aTrees)
			{
				if (tree.m_fWeight > 0 && !tree.m_Prefab.IsEmpty())
					return true;
			}
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] polygon
	//! \param[in] bbox
	//! \param[in] outline
	protected void GenerateOutlineTrees(array<float> polygon, SCR_AABB bbox, ForestGeneratorOutline outline)
	{
		if (!outline || !outline.m_aTreeGroups || outline.m_aTreeGroups.IsEmpty())
			return;

		if (!GetIsAnyTreeValid(outline.m_aTreeGroups))
			return;

		SCR_ETreeType treeType;
		array<ref SCR_ForestGeneratorPoint> currentOutlinePoints;
		array<ref SCR_ForestGeneratorLine> currentOutlineLines;

		switch (outline.m_eOutlineType)
		{
			case SCR_EForestGeneratorOutlineType.SMALL:
			{
				treeType = SCR_ETreeType.SMALL_OUTLINE;
				currentOutlinePoints = m_aSmallOutlinePoints;
				currentOutlineLines = m_aSmallOutlineLines;
				break;
			}

			case SCR_EForestGeneratorOutlineType.MIDDLE:
			{
				treeType = SCR_ETreeType.MIDDLE_OUTLINE;
				currentOutlinePoints = m_aMiddleOutlinePoints;
				currentOutlineLines = m_aMiddleOutlineLines;
				break;
			}
		}

		if (!currentOutlinePoints || !currentOutlineLines)
			return;

		array<float> groupProbas = {}; // test
		array<float> groupCounts = {};
		groupCounts.Resize(outline.m_aTreeGroups.Count());

		vector worldMat[4];
		GetWorldTransform(worldMat);

		bool useScaleCurve = outline.m_fOutlineScaleCurveDistance > 0 && !outline.m_aOutlineScaleCurve.IsEmpty();
		float scaleCurveDistanceDivisor;
		array<float> curveKnots;

		if (useScaleCurve)
		{
			scaleCurveDistanceDivisor = SCALE_CURVE_RANGE / outline.m_fOutlineScaleCurveDistance;
			curveKnots = {};
			foreach (vector scalePoint : outline.m_aOutlineScaleCurve)
			{
				curveKnots.Insert(scalePoint[0]);
			}
		}

		int iterCount = 0;

		vector direction, perpendicular, pointLocal, point;
		float probaSumToNormalize, groupProba, probaSum;
		int groupIdx;
		ForestGeneratorTree tree;
		foreach (SCR_ForestGeneratorLine line : currentOutlineLines)
		{
			direction = line.p2.m_vPos - line.p1.m_vPos;
			perpendicular = { direction[2], 0, -direction[0] };
			perpendicular.Normalize();
			iterCount = outline.m_fDensity * (CalculateAreaForOutline(line, outline) * HECTARE_CONVERSION_FACTOR);
			for (int treeIdx; treeIdx < iterCount; ++treeIdx)
			{
				// generate a point -along- the line (at a perpendicular distance)
				pointLocal = line.p1.m_vPos + (direction * m_RandomGenerator.RandFloat01()) + (perpendicular * SafeRandomFloatInclusive(outline.m_fMinDistance, outline.m_fMaxDistance));
				if (pointLocal == vector.Zero || !Math2D.IsPointInPolygon(polygon, pointLocal[0], pointLocal[2]))
					continue;

				point = pointLocal.Multiply4(worldMat);

				// see which trees are around - count the types
				int groupProbaCount = groupProbas.Copy(outline.m_aGroupProbas);
				for (int i, count = groupCounts.Count(); i < count; i++)
				{
					groupCounts[i] = 1;
				}

				if (s_Benchmark)
					s_Benchmark.BeginMeasure("gridCountEntriesAround");

				m_Grid.CountEntriesAround(point, outline.m_fClusterRadius, groupCounts);

				if (s_Benchmark)
					s_Benchmark.EndMeasure("gridCountEntriesAround");

				// skew the probability of given groups based on counts
				probaSumToNormalize = 0;
				for (int i; i < groupProbaCount; i++)
				{
					groupProbas[i] = groupProbas[i] * Math.Pow(groupCounts[i], outline.m_fClusterStrength);
					probaSumToNormalize += groupProbas[i];
				}

				if (probaSumToNormalize > 0)
				{
					for (int i; i < groupProbaCount; i++)
					{
						groupProbas[i] = groupProbas[i] / probaSumToNormalize;
					}
				}

				groupProba = m_RandomGenerator.RandFloat01();
				groupIdx = groupProbas.Count() - 1; // last because there is less than in the loop
				probaSum = 0;
				for (int i, count = groupProbas.Count(); i < count; ++i)
				{
					probaSum += groupProbas[i];
					if (groupProba < probaSum) // less than to avoid accepting 0 probability tree
					{
						groupIdx = i;
						break;
					}
				}

				tree = SelectTreeToSpawn(point, outline.m_aTreeGroups[groupIdx].m_aTrees);

				if (!IsEntryValid(tree, point, pointLocal))
					continue;

				tree.m_eType = treeType;
				if (useScaleCurve)
				{
					float distanceFromShape = SCR_Math3D.GetDistanceFromSplineXZ(m_aShapePoints, pointLocal);
					if (distanceFromShape <= outline.m_fOutlineScaleCurveDistance)
					{
						// (m_fOutlineScaleCurveDistance - distanceFromShape) because right-to-left curve reading
						float scaleFactor = LegacyCurve.Curve(ECurveType.CatmullRom, (outline.m_fOutlineScaleCurveDistance - distanceFromShape) * scaleCurveDistanceDivisor, outline.m_aOutlineScaleCurve, curveKnots)[1];
						if (scaleFactor < ForestGeneratorLevel.SCALE_CURVE_MIN_VALUE)
							scaleFactor = ForestGeneratorLevel.SCALE_CURVE_MIN_VALUE;
						else
						if (scaleFactor > ForestGeneratorLevel.SCALE_CURVE_MAX_VALUE)
							scaleFactor = ForestGeneratorLevel.SCALE_CURVE_MAX_VALUE;

						tree.m_fScale *= scaleFactor;
					}
				}

				m_Grid.AddEntry(tree, point);
			}
		}

		foreach (SCR_ForestGeneratorPoint currentPoint : currentOutlinePoints)
		{
			iterCount = outline.m_fDensity * CalculateAreaForOutline(currentPoint, outline) * HECTARE_CONVERSION_FACTOR;
			for (int treeIdx; treeIdx < iterCount; treeIdx++)
			{
				pointLocal = GeneratePointInCircle(outline.m_fMinDistance, outline.m_fMaxDistance, currentPoint);

				bool lineDistance1 = IsPointInProperDistanceFromLine(pointLocal, currentPoint.m_Line1, outline.m_fMinDistance, outline.m_fMaxDistance);
				if (!lineDistance1)
					continue;

				bool lineDistance2 = IsPointInProperDistanceFromLine(pointLocal, currentPoint.m_Line2, outline.m_fMinDistance, outline.m_fMaxDistance);
				if (!lineDistance2)
					continue;

				if (!Math2D.IsPointInPolygon(polygon, pointLocal[0], pointLocal[2]))
					continue;

				point = pointLocal.Multiply4(worldMat);

				// see which trees are around - count the types
				groupProbas.Copy(outline.m_aGroupProbas);
				for (int i, count = groupCounts.Count(); i < count; i++)
				{
					groupCounts[i] = 1;
				}

				if (s_Benchmark)
					s_Benchmark.BeginMeasure("gridCountEntriesAround");

				m_Grid.CountEntriesAround(point, outline.m_fClusterRadius, groupCounts);

				if (s_Benchmark)
					s_Benchmark.EndMeasure("gridCountEntriesAround");

				// skew the probability of given groups based on counts
				probaSumToNormalize = 0;
				for (int i, count = groupProbas.Count(); i < count; i++)
				{
					groupProbas[i] = groupProbas[i] * Math.Pow(groupCounts[i], outline.m_fClusterStrength);
					probaSumToNormalize += groupProbas[i];
				}

				if (probaSumToNormalize != 0)
				{
					for (int i, count = groupProbas.Count(); i < count; i++)
					{
						groupProbas[i] = groupProbas[i] / probaSumToNormalize;
					}
				}

				groupProba = m_RandomGenerator.RandFloat01();
				groupIdx = groupProbas.Count() - 1; // last because there is less than in the loop
				probaSum = 0;
				for (int i, count = groupProbas.Count(); i < count; i++)
				{
					probaSum += groupProbas[i];
					if (groupProba < probaSum) // less than to avoid accepting 0 probability tree
					{
						groupIdx = i;
						break;
					}
				}

				tree = SelectTreeToSpawn(point, outline.m_aTreeGroups[groupIdx].m_aTrees);

				if (!IsEntryValid(tree, point, pointLocal))
					continue;

				tree.m_eType = treeType;
				m_Grid.AddEntry(tree, point);
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] point
	//! \param[in] line
	//! \param[in] minDistance
	//! \param[in] maxDistance
	//! \return
	protected bool IsPointInProperDistanceFromLine(vector point, SCR_ForestGeneratorLine line, float minDistance, float maxDistance)
	{
		float distance = Math3D.PointLineSegmentDistance({ point[0], 0, point[2] }, { line.p1.m_vPos[0], 0, line.p1.m_vPos[2] }, { line.p2.m_vPos[0], 0, line.p2.m_vPos[2] });
		return distance >= minDistance && distance <= maxDistance;
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] tree
	//! \param[in] pointWorld
	//! \param[in] pointLocal
	//! \return
	protected bool IsEntryValid(ForestGeneratorTree tree, vector pointWorld, vector pointLocal)
	{
		if (!tree)
			return false;

		if (tree.m_fMaxTerrainSlope < SCR_ForestGeneratorTreeBase.MAX_TERRAIN_SLOPE)
		{
			vector pointW = pointWorld; // to not modify pointWorld
			vector normal = SCR_TerrainHelper.GetTerrainNormal(pointW, GetWorld());

			if (normal[1] < Math.Cos(tree.m_fMaxTerrainSlope * Math.DEG2RAD))
				return false;
		}
		
		FallenTree fallenTree = FallenTree.Cast(tree);
		if (fallenTree)
		{
			float distance;
			float minDistance;
			foreach (SCR_ForestGeneratorLine line : m_aLines)
			{
				distance = Math3D.PointLineSegmentDistance(pointLocal, line.p1.m_vPos, line.p2.m_vPos);
				minDistance = fallenTree.GetMinDistanceFromLine();
				if (distance < minDistance)
					return false;
			}
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] polygon
	//! \param[in] bbox
	//! \param[in] bottomLevel
	protected void GenerateBottomTrees(array<float> polygon, SCR_AABB bbox, ForestGeneratorBottomLevel bottomLevel)
	{
		if (!bottomLevel || bottomLevel.m_aTreeGroups.IsEmpty())
			return;

		if (!GetIsAnyTreeValid(bottomLevel.m_aTreeGroups))
			return;

		array<float> groupProbas = {};
		float totalWeight = 0;
		int groupCount = bottomLevel.m_aTreeGroups.Count();
		groupProbas.Resize(groupCount);
		foreach (TreeGroupClass treeGroup : bottomLevel.m_aTreeGroups)
		{
			totalWeight += treeGroup.m_fWeight;
		}

		if (totalWeight != 0)
		{
			for (int i; i < groupCount; i++)
			{
				groupProbas[i] = (bottomLevel.m_aTreeGroups[i].m_fWeight / totalWeight);
			}
		}

		vector worldMat[4];
		GetWorldTransform(worldMat);

		bool useScaleCurve = bottomLevel.m_fOutlineScaleCurveDistance > 0 && !bottomLevel.m_aOutlineScaleCurve.IsEmpty();
		float scaleCurveDistanceDivisor;
		array<float> curveKnots;

		if (useScaleCurve)
		{
			scaleCurveDistanceDivisor = SCALE_CURVE_RANGE / bottomLevel.m_fOutlineScaleCurveDistance;
			curveKnots = {};
			foreach (vector scalePoint : bottomLevel.m_aOutlineScaleCurve)
			{
				curveKnots.Insert(scalePoint[0]);
			}
		}

		int expectedIterCount = m_fArea * HECTARE_CONVERSION_FACTOR * bottomLevel.m_fDensity;
		vector pointLocal;
		vector point;
		ForestGeneratorTree tree;
		foreach (SCR_ForestGeneratorRectangle rectangle : m_aRectangles)
		{
			int iterCount = bottomLevel.m_fDensity * rectangle.m_fArea * HECTARE_CONVERSION_FACTOR;
			for (int treeIdx; treeIdx < iterCount; ++treeIdx)
			{
				expectedIterCount--;
				// generate random point inside the shape (polygon at first)
				pointLocal = GenerateRandomPointInRectangle(rectangle);

				if (!rectangle.m_aLines.IsEmpty())
				{
					if (!Math2D.IsPointInPolygon(polygon, pointLocal[0], pointLocal[2]))
						continue;

					if (!IsBeforeOutlineBorder(rectangle, pointLocal, bottomLevel.m_fOutlineOverlap))
						continue;
				}

				float perlinValue = Math.PerlinNoise01(pointLocal[0], 0, pointLocal[2]); // TODO Can we change the size of perlin noise?
				if (perlinValue > 1 || perlinValue < 0)
				{
					Print("Perlin value is out of range <0,1>, something went wrong!", LogLevel.ERROR);
					continue;
				}

				float rangeBeginning = 0;
				int groupIdx = 0;
				foreach (int i, float groupProba : groupProbas)
				{
					if (perlinValue > rangeBeginning && perlinValue < (groupProba + rangeBeginning))
					{
						groupIdx = i;
						break;
					}
					rangeBeginning += groupProba;
				}

				point = pointLocal.Multiply4(worldMat);
				tree = SelectTreeToSpawn(point, bottomLevel.m_aTreeGroups[groupIdx].m_aTrees);

				if (!IsEntryValid(tree, point, pointLocal))
					continue;

				tree.m_eType = SCR_ETreeType.BOTTOM;
				tree.m_iDebugGroupIndex = groupIdx;
				if (useScaleCurve)
				{
					float distanceFromShape = SCR_Math3D.GetDistanceFromSplineXZ(m_aShapePoints, pointLocal);
					if (distanceFromShape <= bottomLevel.m_fOutlineScaleCurveDistance)
					{
						// (m_fOutlineScaleCurveDistance - distanceFromShape) because right-to-left curve reading
						float scaleFactor = LegacyCurve.Curve(ECurveType.CatmullRom, (bottomLevel.m_fOutlineScaleCurveDistance - distanceFromShape) * scaleCurveDistanceDivisor, bottomLevel.m_aOutlineScaleCurve, curveKnots)[1];
						if (scaleFactor < ForestGeneratorLevel.SCALE_CURVE_MIN_VALUE)
							scaleFactor = ForestGeneratorLevel.SCALE_CURVE_MIN_VALUE;
						else
						if (scaleFactor > ForestGeneratorLevel.SCALE_CURVE_MAX_VALUE)
							scaleFactor = ForestGeneratorLevel.SCALE_CURVE_MAX_VALUE;

						tree.m_fScale *= scaleFactor;
					}
				}

				m_Grid.AddEntry(tree, point);
			}
		}

		int index;
		while (expectedIterCount > 0)
		{
			index = m_RandomGenerator.RandFloatXY(0, m_aRectangles.Count() - 1);
			GenerateTreeInsideRectangle(m_aRectangles[index], bottomLevel, polygon, worldMat);
			expectedIterCount--;
		}
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] polygon
	//! \param[in] bbox
	//! \param[in] topLevel
	protected void GenerateTopTrees(array<float> polygon, SCR_AABB bbox, ForestGeneratorTopLevel topLevel)
	{
		if (!topLevel || topLevel.m_aTreeGroups.IsEmpty())
			return;

		if (!GetIsAnyTreeValid(topLevel.m_aTreeGroups))
			return;

		array<float> groupProbas = {};
		array<float> groupCounts = {};
		groupCounts.Resize(topLevel.m_aTreeGroups.Count() + TREE_GROUPS_OFFSET_HACK);

		vector worldMat[4];
		GetWorldTransform(worldMat);

		bool useScaleCurve = topLevel.m_fOutlineScaleCurveDistance > 0 && !topLevel.m_aOutlineScaleCurve.IsEmpty();
		float scaleCurveDistanceDivisor;
		array<float> curveKnots;

		if (useScaleCurve)
		{
			scaleCurveDistanceDivisor = SCALE_CURVE_RANGE / topLevel.m_fOutlineScaleCurveDistance;
			curveKnots = {};
			foreach (vector scalePoint : topLevel.m_aOutlineScaleCurve)
			{
				curveKnots.Insert(scalePoint[0]);
			}
		}

		vector pointLocal;
		int expectedIterCount = m_fArea * HECTARE_CONVERSION_FACTOR * topLevel.m_fDensity;
		vector point;
		ForestGeneratorTree tree;

		foreach (SCR_ForestGeneratorRectangle rectangle : m_aRectangles)
		{
			float area = rectangle.m_fArea * HECTARE_CONVERSION_FACTOR;
			int iterCount = topLevel.m_fDensity * area;

			for (int treeIdx; treeIdx < iterCount; ++treeIdx)
			{
				// generate random point inside the shape (polygon at first)
				pointLocal = GenerateRandomPointInRectangle(rectangle);
				expectedIterCount--;

				if (!rectangle.m_aLines.IsEmpty())
				{
					if (!Math2D.IsPointInPolygon(polygon, pointLocal[0], pointLocal[2]))
						continue;

					if (!IsBeforeOutlineBorder(rectangle, pointLocal, topLevel.m_fOutlineOverlap))
						continue;
				}

				point = pointLocal.Multiply4(worldMat);

				// see which trees are around - count the types
				groupProbas.Copy(topLevel.m_aGroupProbas);
				for (int i, count = groupCounts.Count(); i < count; i++)
				{
					groupCounts[i] = 1;
				}

				if (s_Benchmark)
					s_Benchmark.BeginMeasure("gridCountEntriesAround");

				// HERE is the "Invalid tree group index: 1, there are only 1 groups" error source
				m_Grid.CountEntriesAround(point, topLevel.m_fClusterRadius, groupCounts);

				if (s_Benchmark)
					s_Benchmark.EndMeasure("gridCountEntriesAround");

				// skew the probability of given groups based on counts
				float probaSumToNormalize = 0;
				for (int i, count = groupProbas.Count(); i < count; i++)
				{
					groupProbas[i] = groupProbas[i] * Math.Pow(groupCounts[i], topLevel.m_fClusterStrength);
					probaSumToNormalize += groupProbas[i];
				}

				if (probaSumToNormalize != 0)
				{
					for (int i, count = groupProbas.Count(); i < count; i++)
					{
						groupProbas[i] = groupProbas[i] / probaSumToNormalize;
					}
				}

				float groupProba = m_RandomGenerator.RandFloat01();
				int groupIdx = groupProbas.Count() - 1; // last because there is less than in the loop
				float probaSum = 0;
				for (int i, count = groupProbas.Count(); i < count; ++i)
				{
					probaSum += groupProbas[i];
					if (groupProba < probaSum) // less than to avoid accepting 0 probability tree
					{
						groupIdx = i;
						break;
					}
				}

				tree = SelectTreeToSpawn(point, topLevel.m_aTreeGroups[groupIdx].m_aTrees);
				if (!IsEntryValid(tree, point, pointLocal))
					continue;

				tree.m_eType = SCR_ETreeType.TOP;
				if (useScaleCurve)
				{
					float distanceFromShape = SCR_Math3D.GetDistanceFromSplineXZ(m_aShapePoints, pointLocal);
					if (distanceFromShape <= topLevel.m_fOutlineScaleCurveDistance)
					{
						// (m_fOutlineScaleCurveDistance - distanceFromShape) because right-to-left curve reading
						float scaleFactor = LegacyCurve.Curve(ECurveType.CatmullRom, (topLevel.m_fOutlineScaleCurveDistance - distanceFromShape) * scaleCurveDistanceDivisor, topLevel.m_aOutlineScaleCurve, curveKnots)[1];
						if (scaleFactor < ForestGeneratorLevel.SCALE_CURVE_MIN_VALUE)
							scaleFactor = ForestGeneratorLevel.SCALE_CURVE_MIN_VALUE;
						else
						if (scaleFactor > ForestGeneratorLevel.SCALE_CURVE_MAX_VALUE)
							scaleFactor = ForestGeneratorLevel.SCALE_CURVE_MAX_VALUE;

						tree.m_fScale *= scaleFactor;
					}
				}

				m_Grid.AddEntry(tree, point);
			}
		}

		int index;
		while (expectedIterCount > 0)
		{
			index = m_RandomGenerator.RandInt(0, m_aRectangles.Count());
			GenerateTreeInsideRectangle(m_aRectangles[index], topLevel, polygon, worldMat);
			expectedIterCount--;
		}
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] rectangle
	//! \param[in] level
	//! \param[in] polygon
	//! \param[in] worldMat
	protected void GenerateTreeInsideRectangle(notnull SCR_ForestGeneratorRectangle rectangle, notnull SCR_ForestGeneratorTreeLevel level, notnull array<float> polygon, vector worldMat[4])
	{
		array<float> groupProbas = {};
		array<float> groupCounts = {};
		groupCounts.Resize(level.m_aTreeGroups.Count());

		// generate random point inside the shape (polygon at first)
		vector pointLocal = GenerateRandomPointInRectangle(rectangle);

		if (!rectangle.m_aLines.IsEmpty())
		{
			if (!Math2D.IsPointInPolygon(polygon, pointLocal[0], pointLocal[2]))
				return;

			if (!IsBeforeOutlineBorder(rectangle, pointLocal, level.m_fOutlineOverlap))
				return;
		}

		vector point = pointLocal.Multiply4(worldMat);

		// see which trees are around - count the types
		groupProbas.Copy(level.m_aGroupProbas);
		for (int i, count = groupCounts.Count(); i < count; i++)
		{
			groupCounts[i] = 1;
		}

		if (level.m_eType == SCR_EForestGeneratorLevelType.TOP)
		{
			ForestGeneratorTopLevel topLevel = ForestGeneratorTopLevel.Cast(level);
			if (topLevel)
			{
				if (s_Benchmark)
					s_Benchmark.BeginMeasure("gridCountEntriesAround");

				m_Grid.CountEntriesAround(point, topLevel.m_fClusterRadius, groupCounts);

				if (s_Benchmark)
					s_Benchmark.EndMeasure("gridCountEntriesAround");

				// skew the probability of given groups based on counts
				float probaSumToNormalize = 0;
				for (int i, count = groupProbas.Count(); i < count; i++)
				{
					groupProbas[i] = groupProbas[i] * Math.Pow(groupCounts[i], topLevel.m_fClusterStrength);
					probaSumToNormalize += groupProbas[i];
				}

				if (probaSumToNormalize != 0)
				{
					for (int i, count = groupProbas.Count(); i < count; i++)
					{
						groupProbas[i] = groupProbas[i] / probaSumToNormalize;
					}
				}
			}
		}

		float groupProba = m_RandomGenerator.RandFloat01();
		int groupIdx = groupProbas.Count() - 1; // last because there is less than in the loop
		float probaSum = 0;
		for (int i, count = groupProbas.Count(); i < count; ++i)
		{
			probaSum += groupProbas[i];
			if (groupProba < probaSum) // less than to avoid accepting 0 probability tree
			{
				groupIdx = i;
				break;
			}
		}

		if (!level.m_aTreeGroups.IsIndexValid(groupIdx))
			groupIdx = m_RandomGenerator.RandInt(0, level.m_aTreeGroups.Count());

		ForestGeneratorTree tree = SelectTreeToSpawn(point, level.m_aTreeGroups[groupIdx].m_aTrees);
		if (!IsEntryValid(tree, point, pointLocal))
			return;

		tree.m_eType = SCR_ETreeType.TOP;
		m_Grid.AddEntry(tree, point);
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] point
	//! \param[in] trees
	//! \return
	protected ForestGeneratorTree SelectTreeToSpawn(vector point, array<ref ForestGeneratorTree> trees)
	{
		float treeProba = m_RandomGenerator.RandFloat01();
		int treeTypeIdx = trees.Count() - 1; // last because there is less than in the loop
		float probaSum;
		foreach (int i, ForestGeneratorTree tree : trees)
		{
			probaSum += tree.m_fWeight;
			if (treeProba < probaSum) // less than to avoid accepting 0 probability tree
			{
				treeTypeIdx = i;
				break;
			}
		}

		if (s_Benchmark)
			s_Benchmark.BeginMeasure("clone");

		ForestGeneratorTree tree = ForestGeneratorTree.Cast(trees[treeTypeIdx].Clone());

		if (s_Benchmark)
			s_Benchmark.EndMeasure("clone");

		if (!tree)
			return null;

		SetObjectScale(tree);
		FallenTree fallenTree = FallenTree.Cast(tree);
		if (fallenTree)
		{
			fallenTree.m_fYaw = m_RandomGenerator.RandFloat01() * 360;
			fallenTree.Rotate();
		}

		// see if it fits in given place, if not this type is not valid here
		if (m_Grid.IsColliding(point, tree))
			return null;

		/*
		if (fallenTree)
		{
			vector p1 = fallenTree.m_CapsuleStart + point;
			vector p2 = fallenTree.m_CapsuleEnd + point;
			Shape shape = Shape.Create(ShapeType.LINE, ARGB(255, 0, 0, 255), ShapeFlags.NOZBUFFER, p1, p2);
			m_aDebugShapes.Insert(shape);
			shape = Shape.CreateSphere(ARGB(255, 0, 255, 0), ShapeFlags.NOOUTLINE | ShapeFlags.NOZBUFFER, p1, 0.5);
			m_aDebugShapes.Insert(shape);
			shape = Shape.CreateSphere(ARGB(255, 255, 0, 0), ShapeFlags.NOOUTLINE | ShapeFlags.NOZBUFFER, p2, 0.5);
			m_aDebugShapes.Insert(shape);
		}
		*/

		m_aGridEntries.Insert(tree);

		return tree;
	}

	//------------------------------------------------------------------------------------------------
	//! Smooth 2D value noise in 0..1, deterministic for a world position and seedOffset
	protected float PatchNoise(float x, float z, float patchSize, int seedOffset = 0)
	{
		float fx = x / Math.Max(patchSize, 0.01);
		float fz = z / Math.Max(patchSize, 0.01);
		int ix = Math.Floor(fx);
		int iz = Math.Floor(fz);
		float tx = fx - ix;
		float tz = fz - iz;
		tx = tx * tx * (3 - 2 * tx);
		tz = tz * tz * (3 - 2 * tz);

		float a = LatticeHash(ix, iz, seedOffset);
		float b = LatticeHash(ix + 1, iz, seedOffset);
		float c = LatticeHash(ix, iz + 1, seedOffset);
		float d = LatticeHash(ix + 1, iz + 1, seedOffset);

		return Math.Lerp(Math.Lerp(a, b, tx), Math.Lerp(c, d, tx), tz);
	}

	//------------------------------------------------------------------------------------------------
	protected float LatticeHash(int ix, int iz, int seedOffset)
	{
		float v = Math.Sin(ix * 12.9898 + iz * 78.233 + (NOISE_SEED + seedOffset * 101) * 37.719) * 43758.5453;
		return v - Math.Floor(v);
	}

	//------------------------------------------------------------------------------------------------
	//! Spawn probability from slope: full on gentle ground, easing down to a floor on steep ground (never zero)
	protected float GetSlopeDensity(float slopeDeg)
	{
		if (slopeDeg <= SLOPE_DENSITY_FULL_UNTIL)
			return 1;

		if (slopeDeg >= SLOPE_DENSITY_STEEP_AT)
			return SLOPE_DENSITY_MIN;

		return Math.Lerp(1, SLOPE_DENSITY_MIN, (slopeDeg - SLOPE_DENSITY_FULL_UNTIL) / (SLOPE_DENSITY_STEEP_AT - SLOPE_DENSITY_FULL_UNTIL));
	}

	//------------------------------------------------------------------------------------------------
	//! Real-world size [m] of a cluster object: scale * base size of its kind (debris or rock)
	protected float GetPhysicalSize(notnull SCR_ForestGeneratorTreeBase object)
	{
		string prefabPath = object.m_Prefab;
		if (prefabPath.Contains(DEBRIS_KEYWORD))
			return object.m_fScale * DEBRIS_BASE_SIZE;

		return object.m_fScale * ROCK_BASE_SIZE;
	}

	//------------------------------------------------------------------------------------------------
	//! Max slope [degrees] a rock of the given real size can rest on, interpolated in log-size
	protected float GetPhysicalSlopeLimit(float size)
	{
		if (size <= LIMIT_SMALL_SIZE)
			return LIMIT_SMALL_ANGLE;

		if (size >= LIMIT_LARGE_SIZE)
			return LIMIT_LARGE_ANGLE;

		float t = Math.Log2(size / LIMIT_SMALL_SIZE) / Math.Log2(LIMIT_LARGE_SIZE / LIMIT_SMALL_SIZE);
		return Math.Lerp(LIMIT_SMALL_ANGLE, LIMIT_LARGE_ANGLE, t);
	}

	//------------------------------------------------------------------------------------------------
	//! Slope rules for a freshly created cluster object (scale is already set).
	//! Big rocks cannot rest on very steep ground, otherwise density only eases off on steep slopes.
	//! return false if the object must not be spawned
	protected bool ApplyTerrainRules(notnull SCR_ForestGeneratorTreeBase object, vector pointWorld)
	{
		vector samplePos = pointWorld;
		vector normal = SCR_TerrainHelper.GetTerrainNormal(samplePos, GetWorld());
		if (normal.LengthSq() < 0.001)
			return true; // cannot sample, do not interfere

		float slopeDeg = Math.Acos(Math.Clamp(normal[1], -1, 1)) * Math.RAD2DEG;
		m_iStatsTested++;

		float limit = GetPhysicalSlopeLimit(GetPhysicalSize(object));
		if (slopeDeg >= limit)
		{
			m_iStatsRejectedPhysical++;
			return false;
		}

		float probability = GetSlopeDensity(slopeDeg);
		if (slopeDeg > limit - LIMIT_SOFTNESS)
			probability = probability * Math.Clamp((limit - slopeDeg) / LIMIT_SOFTNESS, 0, 1);

		if (probability >= 1 || m_RandomGenerator.RandFloat01() < probability)
			return true;

		m_iStatsRejectedProbability++;
		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] object
	protected void SetObjectScale(notnull SCR_ForestGeneratorTreeBase object)
	{
		object.m_fScale = SafeRandomFloatInclusive(object.m_fMinScale, object.m_fMaxScale);
		object.AdjustScale();
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] rectangle
	//! \param[in] pointLocal
	//! \param[in] additionalDistance
	//! \return whether or not pointLocal is in rectangle's outline
	protected bool IsInOutline(notnull SCR_ForestGeneratorRectangle rectangle, vector pointLocal, float additionalDistance = 0)
	{
		foreach (SCR_ForestGeneratorLine line : rectangle.m_aLines)
		{
			float distance = Math3D.PointLineSegmentDistance(pointLocal, line.p1.m_vPos, line.p2.m_vPos);

			foreach (ForestGeneratorOutline outline : m_aOutlines)
			{
				if (!outline.m_bGenerate)
					continue;

				if (outline.m_eOutlineType == SCR_EForestGeneratorOutlineType.SMALL && !line.p1.m_bSmallOutline)
					continue;

				if (outline.m_eOutlineType == SCR_EForestGeneratorOutlineType.MIDDLE && !line.p1.m_bMiddleOutline)
					continue;

				if (distance > outline.m_fMinDistance - additionalDistance && distance < outline.m_fMaxDistance + additionalDistance)
					return true;
			}
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! same as IsInOutline but reversed
	//! \param[in] rectangle
	//! \param[in] pointLocal
	//! \param[in] offset positive to allow getting closer to shape inside outline, negative to get away from the outline border
	protected bool IsBeforeOutlineBorder(notnull SCR_ForestGeneratorRectangle rectangle, vector pointLocal, float offset = 0)
	{
		foreach (SCR_ForestGeneratorLine line : rectangle.m_aLines)
		{
			float distance = Math3D.PointLineSegmentDistance(pointLocal, line.p1.m_vPos, line.p2.m_vPos);

			foreach (ForestGeneratorOutline outline : m_aOutlines)
			{
				if (!outline.m_bGenerate)
					continue;

				if (outline.m_eOutlineType == SCR_EForestGeneratorOutlineType.SMALL && !line.p1.m_bSmallOutline)
					continue;

				if (outline.m_eOutlineType == SCR_EForestGeneratorOutlineType.MIDDLE && !line.p1.m_bMiddleOutline)
					continue;

				if (distance < outline.m_fMaxDistance - offset)
					return false;
			}
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! \param[in] line
	//! \param[in] outline
	//! \return the outline's surface in square metres
	protected float CalculateAreaForOutline(SCR_ForestGeneratorLine line, ForestGeneratorOutline outline)
	{
		if (!line || !outline)
			return 0;

		return line.m_fLength * (outline.m_fMaxDistance - outline.m_fMinDistance);
	}

	//------------------------------------------------------------------------------------------------
	//!
	//! \param[in] point
	//! \param[in] outline
	//! \return
	protected float CalculateAreaForOutline(SCR_ForestGeneratorPoint point, ForestGeneratorOutline outline)
	{
		if (!point || !outline)
			return 0;

		float areaBigger = Math.PI * outline.m_fMaxDistance * outline.m_fMaxDistance;
		float areaSmaller = Math.PI * outline.m_fMinDistance * outline.m_fMinDistance;

		return (point.m_fAngle / 360) * (areaBigger - areaSmaller);
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnRegenerate()
	{
		super.OnRegenerate();

		RegenerateForest(true);
	}

	//------------------------------------------------------------------------------------------------
	protected override void _WB_OnInit(inout vector mat[4], IEntitySource src)
	{
		super._WB_OnInit(mat, src);
		if (!s_DebugShapeManager)
			s_DebugShapeManager = new SCR_DebugShapeManager();
	}

#endif // WORKBENCH
}
