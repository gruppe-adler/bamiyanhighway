#ifdef WORKBENCH
//! Measures every prefab of the EoH Modular Tunnel Pack: bounds, child entities, and the openings (sockets) on each
//! face of its bounding box, found by tracing against the piece's own collision. Each piece is placed high above the
//! map, measured and deleted again. Results go to $profile:SP_TunnelMeasure.txt.
[WorkbenchPluginAttribute(name: "EoH Tunnel Measure", description: "Measure the EoH Modular Tunnel Pack pieces (bounds and openings)", wbModules: {"WorldEditor"}, awesomeFontCode: 0xF545)]
class SP_TunnelMeasurePlugin : WorldEditorPlugin
{
	protected static const string ROOT = "$EoHModularTunnelPack:Prefabs";
	protected static const string OUT_FILE = "$profile:SP_TunnelMeasure.txt";
	protected static const vector PLACE_AT = "2048 700 2048";
	protected static const float STEP = 0.25;
	protected static const float REACH = 8;

	protected ref array<ResourceName> m_aFound = {};
	protected ref array<IEntity> m_aParts = {};
	protected BaseWorld m_World;
	protected ref FileHandle m_File;	// ref: a plain member let the handle go after the first line

	//------------------------------------------------------------------------------------------------
	override void Run()
	{
		WorldEditor worldEditor = Workbench.GetModule(WorldEditor);
		if (!worldEditor)
			return;

		WorldEditorAPI api = worldEditor.GetApi();
		if (!api)
			return;

		m_World = api.GetWorld();
		m_aFound.Clear();
		Workbench.SearchResources(OnFound, {"et"}, null, ROOT, true);
		m_File = FileIO.OpenFile(OUT_FILE, FileMode.WRITE);
		Line(string.Format("SP_MEASURE %1 prefabs under %2", m_aFound.Count(), ROOT));
		foreach (ResourceName prefab : m_aFound)
		{
			MeasureOne(api, prefab);
		}

		Line("SP_MEASURE done");
		if (m_File)
			m_File.Close();

		m_File = null;
	}

	//------------------------------------------------------------------------------------------------
	protected void OnFound(ResourceName resName, string filePath = "")
	{
		m_aFound.Insert(resName);
	}

	//------------------------------------------------------------------------------------------------
	protected void Line(string text)
	{
		Print(text);
		if (m_File)
			m_File.WriteLine(text);
	}

	//------------------------------------------------------------------------------------------------
	protected void Collect(IEntity entity)
	{
		m_aParts.Insert(entity);
		IEntity child = entity.GetChildren();
		while (child)
		{
			Collect(child);
			child = child.GetSibling();
		}
	}

	//------------------------------------------------------------------------------------------------
	protected bool Hits(vector from, vector to)
	{
		TraceParam trace = new TraceParam();
		trace.Start = from;
		trace.End = to;
		trace.Flags = TraceFlags.ENTS;
		trace.IncludeArray = m_aParts;
		return m_World.TraceMove(trace, null) < 1;
	}

	//------------------------------------------------------------------------------------------------
	protected float Reach(vector from, vector dir)
	{
		TraceParam trace = new TraceParam();
		trace.Start = from;
		trace.End = from + dir * REACH;
		trace.Flags = TraceFlags.ENTS;
		trace.IncludeArray = m_aParts;
		float hit = m_World.TraceMove(trace, null);
		if (hit >= 1)
			return -1;

		return hit * REACH;
	}

	//------------------------------------------------------------------------------------------------
	protected string V(vector v)
	{
		return string.Format("%1 %2 %3", v[0].ToString(6, 3), v[1].ToString(6, 3), v[2].ToString(6, 3));
	}

	//------------------------------------------------------------------------------------------------
	protected void MeasureOne(WorldEditorAPI api, ResourceName prefab)
	{
		api.BeginEntityAction("SP measure");
		IEntitySource src = api.CreateEntity(prefab, "", 0, null, PLACE_AT, vector.Zero);
		api.EndEntityAction();
		if (!src)
		{
			Line("PIECE " + prefab + " FAILED to create");
			return;
		}

		IEntity entity = api.SourceToEntity(src);
		if (entity)
		{
			m_aParts.Clear();
			Collect(entity);
			vector low;
			vector high;
			entity.GetWorldBounds(low, high);
			for (int p = 1; p < m_aParts.Count(); p++)
			{
				vector partLow;
				vector partHigh;
				m_aParts[p].GetWorldBounds(partLow, partHigh);
				for (int axis = 0; axis < 3; axis++)
				{
					low[axis] = Math.Min(low[axis], partLow[axis]);
					high[axis] = Math.Max(high[axis], partHigh[axis]);
				}
			}

			int withPhysics;
			foreach (IEntity part : m_aParts)
			{
				if (part.GetPhysics())
					withPhysics++;
			}

			Line(string.Format("PIECE %1 | min %2 | max %3 | parts %4 physics %5", prefab, V(low - PLACE_AT), V(high - PLACE_AT), m_aParts.Count(), withPhysics));
			for (int c = 1; c < m_aParts.Count(); c++)
			{
				IEntity part = m_aParts[c];
				string partName = part.ClassName();
				EntityPrefabData data = part.GetPrefabData();
				if (data)
					partName += " " + data.GetPrefabName();

				vector angles = part.GetYawPitchRoll();
				Line(string.Format("  CHILD %1 | at %2 | ypr %3 | name '%4'", partName, V(part.GetOrigin() - PLACE_AT), V(angles), part.GetName()));
			}

			// The pack's memory points (snap points), as bones of the model: position and facing, relative to the pivot
			foreach (IEntity mpPart : m_aParts)
			{
				Animation anim = mpPart.GetAnimation();
				if (!anim)
					continue;

				array<string> bones = {};
				anim.GetBoneNames(bones);
				foreach (string bone : bones)
				{
					vector boneMat[4];
					if (!anim.GetBoneMatrix(anim.GetBoneIndex(bone), boneMat))
						continue;

					// bone matrices are in the part's own space; bring them into the piece's space
					vector partMat[4];
					mpPart.GetWorldTransform(partMat);
					vector worldMat[4];
					Math3D.MatrixMultiply4(partMat, boneMat, worldMat);
					Line(string.Format("  MP '%1' | at %2 | fwd %3 | up %4", bone, V(worldMat[3] - PLACE_AT), V(worldMat[2]), V(worldMat[1])));
				}
			}

			for (int face = 0; face < 6; face++)
			{
				ScanFace(face, low, high);
			}
		}

		api.BeginEntityAction("SP measure delete");
		api.DeleteEntity(src);
		api.EndEntityAction();
	}

	//------------------------------------------------------------------------------------------------
	//! One face of the bounding box: a grid of samples, each tested for "open straight in, and walled on all four sides
	//! a little way in". Connected open samples are one opening.
	protected void ScanFace(int face, vector low, vector high)
	{
		int axis = face / 2;
		float sign = 1;
		if (face % 2 == 0)
			sign = -1;

		int axisU = (axis + 1) % 3;
		int axisV = (axis + 2) % 3;
		vector normal = vector.Zero;
		normal[axis] = sign;
		vector dirU = vector.Zero;
		dirU[axisU] = 1;
		vector dirV = vector.Zero;
		dirV[axisV] = 1;
		float plane = low[axis];
		if (sign > 0)
			plane = high[axis];

		int countU = Math.Floor((high[axisU] - low[axisU]) / STEP) + 1;
		int countV = Math.Floor((high[axisV] - low[axisV]) / STEP) + 1;
		if (countU * countV > 40000)
			return;

		array<bool> open = {};
		open.Resize(countU * countV);
		for (int iu = 0; iu < countU; iu++)
		{
			for (int iv = 0; iv < countV; iv++)
			{
				vector point = vector.Zero;
				point[axis] = plane;
				point[axisU] = low[axisU] + iu * STEP;
				point[axisV] = low[axisV] + iv * STEP;
				bool isOpen = !Hits(point + normal * 0.2, point - normal * 0.8);
				if (isOpen)
				{
					vector inside = point - normal * 0.3;
					isOpen = Reach(inside, dirU) > 0 && Reach(inside, -dirU) > 0 && Reach(inside, dirV) > 0 && Reach(inside, -dirV) > 0;
				}

				open[iu * countV + iv] = isOpen;
			}
		}

		// Connected groups of open samples
		array<bool> seen = {};
		seen.Resize(countU * countV);
		array<string> faceNames = {"-X", "+X", "-Y", "+Y", "-Z", "+Z"};
		for (int start = 0; start < open.Count(); start++)
		{
			if (!open[start] || seen[start])
				continue;

			array<int> stack = {start};
			seen[start] = true;
			int minU = 100000;
			int maxU = -1;
			int minV = 100000;
			int maxV = -1;
			int samples;
			while (!stack.IsEmpty())
			{
				int cell = stack[stack.Count() - 1];
				stack.Remove(stack.Count() - 1);
				samples++;
				int cu = cell / countV;
				int cv = cell - cu * countV;
				minU = Math.Min(minU, cu);
				maxU = Math.Max(maxU, cu);
				minV = Math.Min(minV, cv);
				maxV = Math.Max(maxV, cv);
				for (int n = 0; n < 4; n++)
				{
					int nu = cu;
					int nv = cv;
					if (n == 0)
						nu--;
					else if (n == 1)
						nu++;
					else if (n == 2)
						nv--;
					else
						nv++;

					if (nu < 0 || nv < 0 || nu >= countU || nv >= countV)
						continue;

					int next = nu * countV + nv;
					if (open[next] && !seen[next])
					{
						seen[next] = true;
						stack.Insert(next);
					}
				}
			}

			if (samples < 3)
				continue;

			// Refined at the middle: how far the walls are each way, a little way in
			vector middle = vector.Zero;
			middle[axis] = plane;
			middle[axisU] = low[axisU] + (minU + maxU) * 0.5 * STEP;
			middle[axisV] = low[axisV] + (minV + maxV) * 0.5 * STEP;
			vector in = middle - normal * 0.3;
			float uMinus = Reach(in, -dirU);
			float uPlus = Reach(in, dirU);
			float vMinus = Reach(in, -dirV);
			float vPlus = Reach(in, dirV);
			vector exact = in + dirU * ((uPlus - uMinus) * 0.5) + dirV * ((vPlus - vMinus) * 0.5) + normal * 0.3;
			string extra = "";
			if (axis != 1)
			{
				float down = Reach(in, "0 -1 0");
				float up = Reach(in, "0 1 0");
				extra = string.Format(" floorY %1 roofY %2", (in[1] - down - PLACE_AT[1]).ToString(6, 3), (in[1] + up - PLACE_AT[1]).ToString(6, 3));
			}

			Line(string.Format("  OPEN %1 | centre %2 | span %3 x %4 (axes %5,%6) | samples %7%8", faceNames[face], V(exact - PLACE_AT), (uMinus + uPlus).ToString(5, 3), (vMinus + vPlus).ToString(5, 3), axisU, axisV, samples, extra));
		}
	}
}
#endif
