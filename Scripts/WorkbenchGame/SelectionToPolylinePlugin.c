#ifdef WORKBENCH
/*
	Selection to Polyline
	---------------------
	Creates a PolylineShapeEntity through the positions of the currently selected
	entities (e.g. wall segments placed with fixed segment length).

	Usage:
	1. Select the placed wall segments of ONE side of the canal in the World Editor.
	2. Plugins > Selection to Polyline > Create.
	3. Put a WG_ wall generator prefab as child of the new shape (right-click shape).

	Notes:
	- The point is taken at (entity pivot + local offset). If the wall pivot is at the
	  segment START and the segment is 2 m long along +X, the points are the segment
	  starts; the end of the last segment is not included (add it by hand or extend the
	  last segment's point).
	- Selection order is not reliable in the editor, so by default the entities are
	  sorted into a chain by proximity (works for open, non-self-touching paths).
*/
[WorkbenchPluginAttribute(
	name: "Selection to Polyline",
	description: "Creates a polyline shape through the positions of the selected entities",
	wbModules: {"WorldEditor"},
	awesomeFontCode: 0xF5CB
)]
class SelectionToPolylinePlugin : WorldEditorPlugin
{
	[Attribute(defvalue: "0 0 0", desc: "Local offset from each entity's pivot that becomes the polyline point (e.g. '2 0 0' for the end of a 2 m segment along +X)", category: "Points")]
	protected vector m_vLocalOffset;

	[Attribute(defvalue: "1", desc: "Sort entities into a chain by proximity instead of using selection order", category: "Points")]
	protected bool m_bSortIntoChain;

	[Attribute(defvalue: "0", desc: "Reverse the direction of the polyline", category: "Points")]
	protected bool m_bReverse;

	[Attribute(defvalue: "0", desc: "Set each point's height to the terrain surface", category: "Shape")]
	protected bool m_bSnapToTerrain;

	[Attribute(defvalue: "0", desc: "Close the shape", category: "Shape")]
	protected bool m_bIsClosed;

	//------------------------------------------------------------------------------------------------
	override void Run()
	{
		Workbench.ScriptDialog("Selection to Polyline", "Select the wall segments first, then press Create.", this);
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Create", true)]
	protected void ButtonCreate()
	{
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		if (!worldEditor)
			return;

		WorldEditorAPI api = worldEditor.GetApi();
		if (!api)
			return;

		array<vector> points = {};
		int count = api.GetSelectedEntitiesCount();
		for (int i = 0; i < count; i++)
		{
			IEntitySource src = api.GetSelectedEntity(i);
			if (!src)
				continue;

			IEntity ent = api.SourceToEntity(src);
			if (!ent)
				continue;

			vector mat[4];
			ent.GetWorldTransform(mat);
			points.Insert(m_vLocalOffset.Multiply4(mat));
		}

		if (points.Count() < 2)
		{
			Workbench.Dialog("Selection to Polyline", "Select at least two entities.");
			return;
		}

		if (m_bSortIntoChain)
			points = SortIntoChain(points);

		if (m_bReverse)
		{
			array<vector> reversed = {};
			for (int i = points.Count() - 1; i >= 0; i--)
			{
				reversed.Insert(points[i]);
			}
			points = reversed;
		}

		if (m_bSnapToTerrain)
		{
			foreach (int i, vector p : points)
			{
				p[1] = api.GetTerrainSurfaceY(p[0], p[2]);
				points[i] = p;
			}
		}

		IEntitySource shape = CreatePolyline(api, points);
		if (shape)
		{
			api.ClearEntitySelection();
			api.SetEntitySelection(shape);
		}
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Cancel")]
	protected bool ButtonCancel()
	{
		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! Same approach as SCR_ShapeBrushTool: first point is the shape origin, the others are relative to it
	protected IEntitySource CreatePolyline(notnull WorldEditorAPI api, notnull array<vector> points)
	{
		api.BeginEntityAction("Selection to Polyline");

		IEntitySource shape = api.CreateEntity("PolylineShapeEntity", string.Empty, api.GetCurrentEntityLayerId(), null, points[0], vector.Zero);
		if (!shape)
		{
			api.EndEntityAction();
			Workbench.Dialog("Selection to Polyline", "Cannot create PolylineShapeEntity.");
			return null;
		}

		vector origin = points[0];
		foreach (int i, vector point : points)
		{
			if (!api.CreateObjectArrayVariableMember(shape, null, "Points", "ShapePoint", i))
			{
				Print("Cannot create point #" + i, LogLevel.ERROR);
				break;
			}

			if (i == 0) // first point = "0 0 0"
				continue;

			point -= origin;
			api.SetVariableValue(shape, { new ContainerIdPathEntry("Points", i) }, "Position", string.Format("%1 %2 %3", point[0], point[1], point[2]));
		}

		if (m_bIsClosed)
			api.SetVariableValue(shape, null, "IsClosed", "1");

		api.EndEntityAction();
		return shape;
	}

	//------------------------------------------------------------------------------------------------
	//! Start at the point farthest from an arbitrary point (= one end of the path), then always go to the nearest unvisited point
	protected array<vector> SortIntoChain(notnull array<vector> points)
	{
		if (points.Count() < 3)
			return points;

		int startIdx;
		float maxDist = -1;
		foreach (int i, vector p : points)
		{
			float d = vector.DistanceSqXZ(p, points[0]);
			if (d > maxDist)
			{
				maxDist = d;
				startIdx = i;
			}
		}

		array<vector> remaining = {};
		remaining.Copy(points);

		array<vector> result = {};
		result.Insert(remaining[startIdx]);
		remaining.RemoveOrdered(startIdx);

		while (!remaining.IsEmpty())
		{
			vector last = result[result.Count() - 1];
			int nearestIdx;
			float nearestDist = float.MAX;
			foreach (int i, vector p : remaining)
			{
				float d = vector.DistanceSqXZ(p, last);
				if (d < nearestDist)
				{
					nearestDist = d;
					nearestIdx = i;
				}
			}

			result.Insert(remaining[nearestIdx]);
			remaining.RemoveOrdered(nearestIdx);
		}

		return result;
	}
}
#endif